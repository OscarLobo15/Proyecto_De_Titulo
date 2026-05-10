import logging
import re
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from app.models import ProjectAnalysis
from app.services.ai_client import RemoteLLMClient

logger = logging.getLogger(__name__)


class AIModelParseError(RuntimeError):
    pass


class ProjectAnalysisState(TypedDict, total=False):
    user_message: str
    normalized_request: str
    requirements_summary: dict[str, Any]
    stack_recommendation: dict[str, Any]
    analysis: ProjectAnalysis


def build_project_analysis_graph(llm_client: RemoteLLMClient):
    graph = StateGraph(ProjectAnalysisState)

    graph.add_node("receive_user_request", receive_user_request)
    graph.add_node("analyze_requirements", analyze_requirements)
    graph.add_node("select_stack", select_stack)
    graph.add_node("generate_project_plan", lambda state: generate_project_plan(state, llm_client))

    graph.set_entry_point("receive_user_request")
    graph.add_edge("receive_user_request", "analyze_requirements")
    graph.add_edge("analyze_requirements", "select_stack")
    graph.add_edge("select_stack", "generate_project_plan")
    graph.add_edge("generate_project_plan", END)

    return graph.compile()


def analyze_project_with_ai(message: str, llm_client: Optional[RemoteLLMClient] = None) -> ProjectAnalysis:
    client = llm_client or RemoteLLMClient()
    app = build_project_analysis_graph(client)
    logger.info("Starting LangGraph project analysis")
    final_state = app.invoke({"user_message": message})
    analysis = final_state.get("analysis")
    if not isinstance(analysis, ProjectAnalysis):
        raise AIModelParseError("El grafo no produjo una respuesta de analisis valida.")
    return analysis


def receive_user_request(state: ProjectAnalysisState) -> ProjectAnalysisState:
    message = state["user_message"].strip()
    return {"normalized_request": message}


def analyze_requirements(state: ProjectAnalysisState) -> ProjectAnalysisState:
    message = state["normalized_request"]
    lower_message = message.lower()
    modules = []
    for keyword, module in [
        ("usuario", "usuarios"),
        ("auth", "autenticacion"),
        ("autenticacion", "autenticacion"),
        ("autenticación", "autenticacion"),
        ("login", "autenticacion"),
        ("calendario", "calendario"),
        ("reserva", "reservas"),
        ("dashboard", "dashboard"),
        ("admin", "administracion"),
        ("pago", "pagos"),
        ("notificacion", "notificaciones"),
        ("pdf", "documentos"),
        ("pcr", "documentos"),
    ]:
        if keyword in lower_message and module not in modules:
            modules.append(module)

    needs_backend = any(word in lower_message for word in ["api", "backend", "base de datos", "usuarios", "auth", "login", "admin", "reservas"])
    needs_frontend = not any(word in lower_message for word in ["solo api", "api only", "solo backend"])
    needs_database = any(word in lower_message for word in ["base de datos", "usuarios", "reservas", "dashboard", "admin", "persist"])

    return {
        "requirements_summary": {
            "raw_description": message,
            "needs_frontend": needs_frontend,
            "needs_backend": needs_backend,
            "needs_database": needs_database,
            "detected_modules": modules,
        }
    }


def select_stack(state: ProjectAnalysisState) -> ProjectAnalysisState:
    requirements = state["requirements_summary"]
    needs_frontend = requirements["needs_frontend"]
    needs_backend = requirements["needs_backend"]
    needs_database = requirements["needs_database"]

    if needs_frontend and needs_backend:
        project_type = "fullstack"
    elif needs_backend:
        project_type = "api"
    else:
        project_type = "web"

    return {
        "stack_recommendation": {
            "project_type": project_type,
            "frontend": "React + Vite" if needs_frontend else "No requerido",
            "backend": "FastAPI" if needs_backend else "No requerido",
            "database": "PostgreSQL" if needs_database else "No requerida",
            "auth": "Firebase Auth o Supabase Auth" if "autenticacion" in requirements["detected_modules"] else "No definida",
            "deployment": "Docker local inicialmente; Cloud Run si se publica MVP",
        }
    }


def generate_project_plan(state: ProjectAnalysisState, llm_client: RemoteLLMClient) -> ProjectAnalysisState:
    prompt = _build_final_prompt(state)
    raw_response = llm_client.generate(prompt)
    analysis = _stabilize_analysis(_parse_project_analysis(raw_response), state)
    return {"analysis": analysis}


def _build_final_prompt(state: ProjectAnalysisState) -> str:
    return f"""
Eres un arquitecto de software para un generador de proyectos MVP.
Debes responder SOLO con JSON valido, sin markdown, sin explicaciones fuera del JSON.

Descripcion original del usuario:
{state["normalized_request"]}

Analisis preliminar:
{json.dumps(state["requirements_summary"], ensure_ascii=False)}

Stack preliminar:
{json.dumps(state["stack_recommendation"], ensure_ascii=False)}

Devuelve exactamente este contrato:
{{
  "project_type": "web | api | fullstack",
  "frontend": "stack frontend recomendado o No requerido",
  "backend": "stack backend recomendado o No requerido",
  "database": "base de datos recomendada o No requerida",
  "auth": "estrategia de autenticacion",
  "deployment": "estrategia de despliegue",
  "required_modules": ["modulo 1", "modulo 2"],
  "recommended_templates": ["template 1", "template 2"],
  "notes": "observaciones tecnicas breves"
}}

Reglas:
- Si el usuario necesita usuarios, reservas, administracion o datos persistentes, recomienda backend.
- Si hay backend y datos persistentes, recomienda base de datos.
- No prometas generacion completa de archivos todavia; esto es solo analisis.
- Usa nombres compatibles con un generador React/FastAPI/PostgreSQL/Firebase/Docker/LangGraph.
- En recommended_templates usa solo nombres existentes del generador: base, frontend-react, backend-fastapi, auth-firebase, docker, services, cloud-gcp, cloud-aws, cloud-azure.
- No contradigas en notes los campos frontend, backend, database, auth o deployment.
""".strip()


def _parse_project_analysis(raw_response: str) -> ProjectAnalysis:
    json_text = _extract_json_object(raw_response)
    try:
        payload = json.loads(json_text)
        return ProjectAnalysis.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        logger.warning("AI model returned non-parseable project analysis: %s", raw_response[:500])
        raise AIModelParseError("El modelo devolvio texto no parseable como JSON estructurado.") from exc


def _extract_json_object(raw_response: str) -> str:
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, flags=re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    start = raw_response.find("{")
    end = raw_response.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AIModelParseError("El modelo no devolvio un objeto JSON.")
    return raw_response[start : end + 1]


def _stabilize_analysis(analysis: ProjectAnalysis, state: ProjectAnalysisState) -> ProjectAnalysis:
    requirements = state["requirements_summary"]
    stack = state["stack_recommendation"]
    detected_modules = requirements["detected_modules"]
    project_type = analysis.project_type if analysis.project_type in {"web", "api", "fullstack"} else stack["project_type"]

    auth = analysis.auth
    if "autenticacion" in detected_modules and _is_empty_recommendation(auth):
        auth = "Firebase Auth o Supabase Auth"

    required_modules = _unique([*detected_modules, *analysis.required_modules])

    stabilized = ProjectAnalysis(
        project_type=project_type,
        frontend=_normalize_frontend(analysis.frontend or stack["frontend"]),
        backend=_normalize_backend(analysis.backend or stack["backend"]),
        database=_normalize_database(analysis.database or stack["database"]),
        auth=_normalize_auth(auth or stack["auth"]),
        deployment=_normalize_deployment(analysis.deployment or stack["deployment"]),
        required_modules=required_modules,
        recommended_templates=_recommended_templates_for(project_type, auth, analysis.deployment),
        notes=analysis.notes,
    )
    return stabilized


def _recommended_templates_for(project_type: str, auth: str, deployment: str) -> list[str]:
    templates = ["base"]
    if project_type in {"web", "fullstack"}:
        templates.append("frontend-react")
    if project_type in {"api", "fullstack"}:
        templates.append("backend-fastapi")
    if "firebase" in auth.lower() and project_type in {"web", "fullstack"}:
        templates.append("auth-firebase")
    templates.append("docker")
    if "cloud run" in deployment.lower() or "gcp" in deployment.lower():
        templates.append("cloud-gcp")
    return templates


def _is_empty_recommendation(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"", "no definida", "no definido", "no requerido", "no requerida", "none"}


def _unique(values: list[str]) -> list[str]:
    cleaned = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _normalize_frontend(value: str) -> str:
    normalized = value.lower()
    if "no requerido" in normalized or "no requerida" in normalized:
        return "No requerido"
    if "react" in normalized or "vite" in normalized:
        return "React + Vite"
    return value


def _normalize_backend(value: str) -> str:
    normalized = value.lower()
    if "no requerido" in normalized or "no requerida" in normalized:
        return "No requerido"
    if "fastapi" in normalized:
        return "FastAPI"
    return value


def _normalize_database(value: str) -> str:
    normalized = value.lower()
    if "no requerida" in normalized or "no requerido" in normalized:
        return "No requerida"
    if "postgres" in normalized:
        return "PostgreSQL"
    if "firestore" in normalized:
        return "Firestore"
    if "supabase" in normalized:
        return "Supabase Postgres"
    return value


def _normalize_auth(value: str) -> str:
    normalized = value.lower()
    if "no definida" in normalized or "no requerido" in normalized or "no requerida" in normalized:
        return value
    if "firebase" in normalized:
        return "Firebase Auth"
    if "supabase" in normalized:
        return "Supabase Auth"
    return value


def _normalize_deployment(value: str) -> str:
    normalized = value.lower()
    if "cloud run" in normalized:
        return "Docker local inicialmente; Cloud Run para despliegue"
    if "docker" in normalized:
        return "Docker local"
    return value
