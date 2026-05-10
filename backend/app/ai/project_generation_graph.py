import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.config import settings
from app.generator import ProjectGenerator
from app.models import ProjectConfig
from app.services.ai_client import RemoteLLMClient

logger = logging.getLogger(__name__)


class AIGenerationError(RuntimeError):
    pass


class TemplateSelectionError(AIGenerationError):
    pass


class ProjectGenerationState(TypedDict, total=False):
    prompt: str
    project_name: str
    normalized_prompt: str
    llm_requirements: dict[str, Any]
    requirements: dict[str, Any]
    selected_architecture: dict[str, Any]
    selected_templates: list[str]
    project_config: ProjectConfig
    zip_path: Path
    file_name: str
    download_url: str
    install_command: str
    install_command_windows: Optional[str]
    message: str


REAL_TEMPLATE_GROUPS = {
    "base",
    "frontend-react",
    "backend-fastapi",
    "auth-firebase",
    "docker",
    "services",
    "cloud-gcp",
    "cloud-aws",
    "cloud-azure",
}


def build_project_generation_graph(llm_client: Optional[RemoteLLMClient] = None):
    client = llm_client or RemoteLLMClient(timeout_seconds=settings.ai_project_generation_timeout_seconds)
    graph = StateGraph(ProjectGenerationState)

    graph.add_node("receive_user_request", receive_user_request)
    graph.add_node("analyze_requirements", lambda state: analyze_requirements(state, client))
    graph.add_node("select_architecture", select_architecture)
    graph.add_node("select_templates", select_templates)
    graph.add_node("validate_template_selection", validate_template_selection)
    graph.add_node("generate_project_config", generate_project_config)
    graph.add_node("call_project_generator", call_project_generator)
    graph.add_node("package_project", package_project)
    graph.add_node("return_download_response", return_download_response)

    graph.set_entry_point("receive_user_request")
    graph.add_edge("receive_user_request", "analyze_requirements")
    graph.add_edge("analyze_requirements", "select_architecture")
    graph.add_edge("select_architecture", "select_templates")
    graph.add_edge("select_templates", "validate_template_selection")
    graph.add_edge("validate_template_selection", "generate_project_config")
    graph.add_edge("generate_project_config", "call_project_generator")
    graph.add_edge("call_project_generator", "package_project")
    graph.add_edge("package_project", "return_download_response")
    graph.add_edge("return_download_response", END)

    return graph.compile()


def generate_project_with_ai(prompt: str, project_name: str, llm_client: Optional[RemoteLLMClient] = None) -> ProjectGenerationState:
    logger.info("Starting AI project generation graph for %s", project_name)
    app = build_project_generation_graph(llm_client)
    final_state = app.invoke({"prompt": prompt, "project_name": project_name})
    if not final_state.get("zip_path"):
        raise AIGenerationError("El grafo IA no produjo un ZIP descargable.")
    return final_state


def receive_user_request(state: ProjectGenerationState) -> ProjectGenerationState:
    logger.info("AI graph node: receive_user_request")
    return {
        "normalized_prompt": state["prompt"].strip(),
        "project_name": state["project_name"].strip().lower().replace(" ", "-"),
    }


def analyze_requirements(state: ProjectGenerationState, llm_client: RemoteLLMClient) -> ProjectGenerationState:
    logger.info("AI graph node: analyze_requirements")
    heuristic_requirements = _heuristic_requirements(state["normalized_prompt"])
    prompt = _build_requirements_prompt(state["normalized_prompt"])
    raw_response = llm_client.generate(prompt)
    llm_requirements = _extract_json(raw_response)
    requirements = _merge_requirements(heuristic_requirements, llm_requirements)
    requirements["analysis_source"] = "llm"
    return {"llm_requirements": llm_requirements, "requirements": requirements}


def select_architecture(state: ProjectGenerationState) -> ProjectGenerationState:
    logger.info("AI graph node: select_architecture")
    requirements = state["requirements"]
    needs_frontend = bool(requirements["needs_frontend"])
    needs_backend = bool(requirements["needs_backend"])
    needs_database = bool(requirements["needs_database"])
    needs_auth = bool(requirements["needs_auth"])
    needs_docker = bool(requirements["needs_docker"])
    cloud_target = _normalize_cloud(requirements.get("cloud_target", "local"), state["normalized_prompt"])

    if needs_frontend and needs_backend:
        project_type = "fullstack"
    elif needs_backend:
        project_type = "api"
    else:
        project_type = "web"

    architecture = {
        "project_type": project_type,
        "frontend": "react" if needs_frontend else "none",
        "backend": "fastapi" if needs_backend else "none",
        "database": "postgresql" if needs_database and needs_backend else "none",
        "auth": "firebase" if needs_auth and needs_frontend else "none",
        "include_docker": needs_docker,
        "cloud": cloud_target,
        "project_profile": "standard",
        "include_langgraph": False,
        "include_services": False,
        "service_count": 0,
        "target_os": "mac",
        "modules": requirements["functional_modules"],
        "roles": requirements["user_roles"],
        "future_integrations": requirements["future_integrations"],
        "constraints": requirements["technical_constraints"],
        "analysis_source": requirements.get("analysis_source", "llm"),
    }
    return {"selected_architecture": architecture}


def select_templates(state: ProjectGenerationState) -> ProjectGenerationState:
    logger.info("AI graph node: select_templates")
    architecture = state["selected_architecture"]
    templates = ["base"]

    if architecture["project_type"] in {"web", "fullstack"}:
        templates.append("frontend-react")
    if architecture["project_type"] in {"api", "fullstack"}:
        templates.append("backend-fastapi")
    if architecture["auth"] == "firebase" and architecture["project_type"] in {"web", "fullstack"}:
        templates.append("auth-firebase")
    if architecture["include_docker"]:
        templates.append("docker")
    if architecture["include_services"]:
        templates.append("services")
    if architecture["cloud"] != "local":
        templates.append(f"cloud-{architecture['cloud']}")

    return {"selected_templates": _unique(templates)}


def validate_template_selection(state: ProjectGenerationState) -> ProjectGenerationState:
    logger.info("AI graph node: validate_template_selection")
    templates = state["selected_templates"]
    architecture = state["selected_architecture"]

    missing = [template for template in templates if not (settings.templates_dir / template).exists()]
    if missing:
        raise TemplateSelectionError(f"Templates inexistentes: {', '.join(missing)}")

    if architecture["project_type"] in {"api", "fullstack"} and "backend-fastapi" not in templates:
        raise TemplateSelectionError("Falta template critico backend-fastapi.")
    if architecture["project_type"] in {"web", "fullstack"} and "frontend-react" not in templates:
        raise TemplateSelectionError("Falta template critico frontend-react.")

    safe_templates = [template for template in templates if template in REAL_TEMPLATE_GROUPS]
    return {"selected_templates": safe_templates}


def generate_project_config(state: ProjectGenerationState) -> ProjectGenerationState:
    logger.info("AI graph node: generate_project_config")
    architecture = state["selected_architecture"]
    project_type = architecture["project_type"]

    containers = []
    if project_type in {"web", "fullstack"}:
        containers.append("frontend")
    if project_type in {"api", "fullstack"}:
        containers.append("backend")
    if architecture["include_services"]:
        containers.append("services")

    description = state["normalized_prompt"][:180] or "Proyecto generado con IA."
    config = ProjectConfig(
        project_name=state["project_name"],
        description=description,
        project_type=project_type,
        project_profile=architecture["project_profile"],
        frontend="react",
        backend="fastapi",
        auth=architecture["auth"],
        database=architecture["database"],
        cloud=architecture["cloud"],
        containers=containers,
        include_docker=architecture["include_docker"],
        include_dev_script=True,
        include_services=architecture["include_services"],
        include_langgraph=architecture["include_langgraph"],
        service_count=architecture["service_count"],
        target_os=architecture["target_os"],
        functional_modules=architecture["modules"],
        user_roles=architecture["roles"],
    )
    return {"project_config": config}


def call_project_generator(state: ProjectGenerationState) -> ProjectGenerationState:
    logger.info("AI graph node: call_project_generator")
    try:
        zip_path = ProjectGenerator(settings.templates_dir, settings.generated_dir).generate(state["project_config"])
    except (FileNotFoundError, ValueError) as exc:
        raise AIGenerationError(f"No fue posible generar el proyecto: {exc}") from exc
    return {"zip_path": zip_path}


def package_project(state: ProjectGenerationState) -> ProjectGenerationState:
    logger.info("AI graph node: package_project")
    zip_path = state["zip_path"]
    if not zip_path.exists() or zip_path.suffix != ".zip":
        raise AIGenerationError("El empaquetado fallo: ZIP no encontrado.")
    return {"file_name": zip_path.name, "download_url": f"{settings.public_url}/download/{zip_path.name}"}


def return_download_response(state: ProjectGenerationState) -> ProjectGenerationState:
    logger.info("AI graph node: return_download_response")
    config = state["project_config"]
    token = _encode_config(config)
    install_command_windows = f'iwr "{settings.public_url}/install/{token}/ps1" | iex' if config.target_os in ("windows", "both") else None
    return {
        "install_command": f'curl -fsSL "{settings.public_url}/install/{token}" | bash',
        "install_command_windows": install_command_windows,
        "message": "Proyecto generado correctamente con IA",
    }


def _build_requirements_prompt(user_prompt: str) -> str:
    return f"""
Eres un analista tecnico para una plataforma generadora de arquitecturas base.
Responde SOLO con JSON valido, sin markdown.

Texto del usuario:
{user_prompt}

Extrae este contrato:
{{
  "project_type": "web | api | fullstack | unknown",
  "functional_modules": ["modulo"],
  "user_roles": ["rol"],
  "needs_auth": true,
  "needs_database": true,
  "needs_deployment": true,
  "needs_docker": true,
  "cloud_target": "local | gcp | aws | azure | unknown",
  "future_integrations": ["integracion"],
  "technical_constraints": ["restriccion"]
}}
""".strip()


def _heuristic_requirements(prompt: str) -> dict[str, Any]:
    lower_prompt = prompt.lower()
    modules = []
    roles = []
    integrations = []
    constraints = []

    for keyword, module in [
        ("reserva", "reservas"),
        ("calendario", "calendario"),
        ("dashboard", "dashboard"),
        ("admin", "administracion"),
        ("paciente", "pacientes"),
        ("psicologo", "psicologos"),
        ("psicólogo", "psicologos"),
        ("pago", "pagos"),
        ("notificacion", "notificaciones"),
        ("pdf", "documentos"),
        ("pcr", "documentos"),
    ]:
        if keyword in lower_prompt:
            modules.append(module)

    for keyword, role in [
        ("paciente", "paciente"),
        ("psicologo", "psicologo"),
        ("psicólogo", "psicologo"),
        ("admin", "administrador"),
        ("usuario", "usuario"),
    ]:
        if keyword in lower_prompt:
            roles.append(role)

    if "pdf" in lower_prompt or "pcr" in lower_prompt:
        integrations.append("upload-pdf-pcr")
    if "cloud" in lower_prompt or "despliegue" in lower_prompt:
        constraints.append("preparado para despliegue cloud")

    needs_auth = any(word in lower_prompt for word in ["auth", "autenticacion", "autenticación", "login", "usuarios"])
    needs_database = any(word in lower_prompt for word in ["postgres", "base de datos", "reservas", "pacientes", "dashboard"])
    needs_backend = needs_database or needs_auth or any(word in lower_prompt for word in ["api", "backend", "admin"])
    needs_frontend = not any(word in lower_prompt for word in ["solo api", "api only", "solo backend"])

    return {
        "raw_prompt": prompt,
        "project_type": "fullstack" if needs_frontend and needs_backend else "api" if needs_backend else "web",
        "functional_modules": _unique(modules),
        "user_roles": _unique(roles),
        "needs_auth": needs_auth,
        "needs_database": needs_database,
        "needs_deployment": "cloud" in lower_prompt or "despliegue" in lower_prompt,
        "needs_docker": "docker" in lower_prompt or "contenedor" in lower_prompt or "cloud" in lower_prompt,
        "cloud_target": "gcp" if "gcp" in lower_prompt or "cloud run" in lower_prompt or "cloud" in lower_prompt else "local",
        "future_integrations": _unique(integrations),
        "technical_constraints": _unique(constraints),
        "needs_frontend": needs_frontend,
        "needs_backend": needs_backend,
    }


def _merge_requirements(heuristic: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
    project_type = _normalize_project_type(llm.get("project_type")) or heuristic["project_type"]
    if project_type == "fullstack":
        needs_frontend = True
        needs_backend = True
    elif project_type == "api":
        needs_frontend = False
        needs_backend = True
    elif project_type == "web":
        needs_frontend = True
        needs_backend = False
    else:
        needs_frontend = heuristic["needs_frontend"]
        needs_backend = heuristic["needs_backend"]

    return {
        "project_type": project_type,
        "functional_modules": _unique([*heuristic["functional_modules"], *_as_list(llm.get("functional_modules"))]),
        "user_roles": _unique([*heuristic["user_roles"], *_as_list(llm.get("user_roles"))]),
        "needs_auth": bool(llm.get("needs_auth", heuristic["needs_auth"])) or heuristic["needs_auth"],
        "needs_database": bool(llm.get("needs_database", heuristic["needs_database"])) or heuristic["needs_database"],
        "needs_deployment": bool(llm.get("needs_deployment", heuristic["needs_deployment"])) or heuristic["needs_deployment"],
        "needs_docker": bool(llm.get("needs_docker", heuristic["needs_docker"])) or heuristic["needs_docker"],
        "cloud_target": _normalize_cloud(llm.get("cloud_target"), heuristic["raw_prompt"]) if llm.get("cloud_target") else heuristic["cloud_target"],
        "future_integrations": _unique([*heuristic["future_integrations"], *_as_list(llm.get("future_integrations"))]),
        "technical_constraints": _unique([*heuristic["technical_constraints"], *_as_list(llm.get("technical_constraints"))]),
        "needs_frontend": needs_frontend,
        "needs_backend": needs_backend,
    }


def _extract_json(raw_response: str) -> dict[str, Any]:
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, flags=re.DOTALL)
    json_text = fenced_match.group(1) if fenced_match else raw_response[raw_response.find("{") : raw_response.rfind("}") + 1]
    try:
        payload = json.loads(json_text)
    except (TypeError, json.JSONDecodeError) as exc:
        logger.warning("LLM response is not valid JSON for project generation: %s", raw_response[:500])
        raise AIGenerationError("El LLM remoto devolvio una respuesta invalida para generar el proyecto.") from exc
    if not isinstance(payload, dict):
        raise AIGenerationError("El LLM remoto no devolvio un objeto JSON.")
    return payload


def _encode_config(config: ProjectConfig) -> str:
    payload = json.dumps(config.model_dump(), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _normalize_project_type(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"web", "api", "fullstack"} else None


def _normalize_cloud(value: Any, prompt: str = "") -> str:
    lower_prompt = prompt.lower()
    if "aws" not in lower_prompt and "azure" not in lower_prompt and ("cloud" in lower_prompt or "despliegue" in lower_prompt):
        return "gcp"
    normalized = str(value or "local").strip().lower()
    if normalized in {"gcp", "aws", "azure"}:
        return normalized
    if "cloud run" in normalized or "google" in normalized:
        return "gcp"
    return "local"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip().lower()]
    return []


def _unique(values: list[str]) -> list[str]:
    cleaned = []
    for value in values:
        normalized = str(value).strip().lower()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned
