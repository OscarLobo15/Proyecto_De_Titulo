import base64
import json
import logging
import re
import unicodedata
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


def _extract_name_from_text(text: str) -> Optional[str]:
    if re.search(r"\bdigital\s+workers?\b", text, flags=re.IGNORECASE):
        return "digital-workers"
    if re.search(r"\bGRC\b|\bGovernance,\s*Risk\s*&\s*Compliance\b", text, flags=re.IGNORECASE):
        return "grc-digital-workers"
    m = re.search(
        r'["“”«»]([A-Za-zà-ÿ][A-Za-zà-ÿ0-9\s\-]{2,40})["“”«»]',
        text,
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r'\b(?:llamad[ao]|se llama)\s+([A-ZÀ-ÖØ-Þ][A-Za-zà-ÿ0-9\-]{2,40})',
        text,
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r'\b(?:proyecto|sistema|plataforma|aplicaci[oó]n|app|portal|herramienta|software|servicio)\s+([A-ZÀ-ÖØ-Þ][A-Za-zà-ÿ0-9\-]{2,40})',
        text,
    )
    if m:
        return m.group(1).strip()
    return None


def _slugify_name(name: str) -> str:
    normalized = unicodedata.normalize("NFD", name)
    ascii_name = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:60] or "proyecto"


def _generate_project_name_with_llm(description: str, client: RemoteLLMClient) -> str:
    prompt = (
        "Based on the following project description, generate a short, descriptive project name "
        "as a slug (lowercase, hyphen-separated, 2-5 words, no accents, no special characters).\n"
        f"Project description:\n{description[:800]}\n"
        "Respond with ONLY the slug name, nothing else."
    )
    try:
        raw = client.generate(prompt).strip()
        first_line = raw.split("\n")[0].strip().strip("\"'").lower()
        slug = re.sub(r"[^a-z0-9]+", "-", first_line).strip("-")
        if len(slug) >= 3:
            return slug[:60]
    except Exception as exc:
        logger.warning("LLM name generation failed: %s", exc)
    return "proyecto-ia"


def _resolve_project_name(description: str, project_name: Optional[str], client: RemoteLLMClient) -> str:
    if project_name and len(project_name.strip()) >= 3:
        return _slugify_name(project_name.strip())
    extracted = _extract_name_from_text(description)
    if extracted:
        slug = _slugify_name(extracted)
        if len(slug) >= 3:
            return slug
    return _generate_project_name_with_llm(description, client)


def generate_project_with_ai(prompt: str, project_name: Optional[str] = None, llm_client: Optional[RemoteLLMClient] = None) -> ProjectGenerationState:
    client = llm_client or RemoteLLMClient()
    resolved_name = _resolve_project_name(prompt, project_name, client)
    logger.info("Starting AI project generation graph for %s", resolved_name)
    app = build_project_generation_graph(client)
    final_state = app.invoke({"prompt": prompt, "project_name": resolved_name})
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

    modules = _curate_functional_modules(requirements["functional_modules"])
    roles = _curate_user_roles(requirements["user_roles"])
    project_profile = _derive_project_profile(state["normalized_prompt"], modules)
    include_services, service_count = _derive_service_layout(state["normalized_prompt"], project_profile, project_type)
    include_langgraph = project_profile == "ai" and project_type != "web"

    architecture = {
        "project_type": project_type,
        "frontend": "react" if needs_frontend else "none",
        "backend": "fastapi" if needs_backend else "none",
        "database": "postgresql" if needs_database and needs_backend else "none",
        "auth": "firebase" if needs_auth and needs_frontend else "none",
        "include_docker": needs_docker,
        "cloud": cloud_target,
        "project_profile": project_profile,
        "include_langgraph": include_langgraph,
        "include_services": include_services,
        "service_count": service_count,
        "target_os": "mac",
        "modules": modules,
        "roles": roles,
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
        navigation_layout="sidebar",
        login_variant="digital-workers" if architecture["project_profile"] == "ai" else "ibm-classic",
        experience_mode=_derive_experience_mode(architecture["roles"]),
        admin_style="business" if _derive_experience_mode(architecture["roles"]) == "user" else "operations",
        navigation_sections=_derive_navigation_sections(architecture["modules"], architecture["project_profile"]),
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
Eres un analista tecnico senior para una plataforma generadora de arquitecturas base.
Responde SOLO con JSON valido, sin markdown.

Texto del usuario:
{user_prompt}

Analiza el texto como requerimientos de negocio y técnicos. Si es un PCR, SOW, contrato,
licitación o documento extenso, identifica primero el objetivo real del servicio y separa
contenido contractual/legal de capacidades funcionales del sistema.

Extrae este contrato JSON:
{{
  "business_goal": "objetivo real del proyecto en una frase",
  "domain_context": "dominio, industria o proceso principal",
  "project_type": "web | api | fullstack | unknown",
  "functional_modules": [
    {{
      "name": "modulo funcional especifico",
      "evidence": "frase corta copiada o parafraseada del texto que justifica el modulo",
      "confidence": 0.0
    }}
  ],
  "user_roles": [
    {{
      "name": "rol operativo real",
      "evidence": "frase corta del texto que justifica el rol",
      "confidence": 0.0
    }}
  ],
  "needs_auth": true,
  "needs_database": true,
  "needs_deployment": true,
  "needs_docker": true,
  "cloud_target": "local | gcp | aws | azure | unknown",
  "future_integrations": ["integracion"],
  "technical_constraints": ["restriccion"]
}}

Reglas de fidelidad:
- No inventes módulos por palabras aisladas. Cada modulo y rol debe tener evidencia concreta en el texto.
- Ignora boilerplate legal, tabla de contenidos, firmas, precios, condiciones de pago, RUTs, confidencialidad y anexos contractuales si no describen comportamiento del sistema.
- Prefiere nombres de módulos específicos del dominio del documento por sobre categorías genéricas.
- No uses "usuario" como rol si el documento permite identificar roles operativos más precisos.
- No conviertas actividades de delivery, RACI o plan de trabajo en módulos o roles. Ejemplos inválidos: "definir casos de uso", "provisión de accesos", "diseño funcional", "preparar datasets", "implementación y pruebas", "validación human-in-the-loop por área", "promoción a producción".
- Los roles son actores/personas/equipos que usan, aprueban u operan el sistema. Los módulos son capacidades del producto final. Las tareas del proyecto no son ni roles ni módulos.
- No uses nombres de empresas, razones sociales, proveedores o partes contractuales como roles. Ejemplos inválidos: "LATAM Airlines Group S.A.", "IBM Chile SpA". Si aparecen, identifica el equipo operativo concreto asociado, por ejemplo "equipo ciberseguridad", "área cumplimiento", "aprobador cliente", "equipo IBM delivery".
- Si algo no está suficientemente sustentado en el texto, no lo incluyas.
""".strip()


def _heuristic_requirements(prompt: str) -> dict[str, Any]:
    lower_prompt = prompt.lower()
    modules = []
    roles = []
    integrations = []
    constraints = []

    for keyword, module in [
        ("digital worker", "digital-workers"),
        ("digital skills", "skills-tasks"),
        ("digital tasks", "skills-tasks"),
        ("human-in-the-loop", "human-in-the-loop"),
        ("orquestacion", "orquestacion"),
        ("orquestación", "orquestacion"),
        ("calendario", "reuniones"),
        ("dashboard", "dashboard"),
        ("admin", "administracion"),
        ("paciente", "pacientes"),
        ("psicologo", "psicologos"),
        ("psicólogo", "psicologos"),
        ("notificacion", "notificaciones"),
        ("pdf", "documentos"),
        ("pcr", "documentos"),
        ("okr", "okrs"),
        ("onboarding", "onboarding"),
        ("jira", "tickets"),
        ("crisis", "gestion-crisis"),
        ("regulacion", "regulaciones"),
        ("regulación", "regulaciones"),
        ("cuestionario", "cuestionarios"),
        ("cumplimiento", "cumplimiento"),
        ("ciberseguridad", "ciberseguridad"),
        ("google workspace", "integraciones"),
    ]:
        if keyword in lower_prompt:
            modules.append(module)

    if _has_business_context(lower_prompt, ["reserva", "reservas"], ["agenda", "calendario", "cita", "booking"]):
        modules.append("reservas")
    if _has_business_context(lower_prompt, ["pago", "pagos", "cobro", "cobros"], ["checkout", "facturacion", "facturación", "transaccion", "transacción"]):
        modules.append("pagos")

    for keyword, role in [
        ("paciente", "paciente"),
        ("psicologo", "psicologo"),
        ("psicólogo", "psicologo"),
        ("admin", "administrador"),
        ("usuario autorizado", "aprobador-cliente"),
        ("human-in-the-loop", "aprobador-cliente"),
        ("cumplimiento", "analista-cumplimiento"),
        ("ciberseguridad", "equipo-ciberseguridad"),
        ("auditor", "auditor"),
        ("operador", "operador"),
    ]:
        if keyword in lower_prompt:
            roles.append(role)

    if "pdf" in lower_prompt or "pcr" in lower_prompt:
        integrations.append("upload-pdf-pcr")
    if "cloud" in lower_prompt or "despliegue" in lower_prompt:
        constraints.append("preparado para despliegue cloud")

    needs_auth = any(word in lower_prompt for word in ["auth", "autenticacion", "autenticación", "login", "usuarios", "usuario autorizado", "aprobada por un usuario"])
    needs_database = any(word in lower_prompt for word in ["postgres", "base de datos", "base de conocimiento", "repositorio", "dashboard", "trazabilidad", "almacen"])
    needs_backend = needs_database or needs_auth or any(word in lower_prompt for word in ["api", "backend", "admin", "integracion", "integración"])
    needs_frontend = not any(word in lower_prompt for word in ["solo api", "api only", "solo backend"])

    return {
        "raw_prompt": prompt,
        "project_type": "fullstack" if needs_frontend and needs_backend else "api" if needs_backend else "web",
        "functional_modules": _unique(modules),
        "user_roles": _unique(roles),
        "needs_auth": needs_auth,
        "needs_database": needs_database,
        "needs_deployment": "cloud" in lower_prompt or "despliegue" in lower_prompt or "producción" in lower_prompt or "produccion" in lower_prompt,
        "needs_docker": "docker" in lower_prompt or "contenedor" in lower_prompt or "cloud" in lower_prompt or "cloud-native" in lower_prompt,
        "cloud_target": "gcp" if "gcp" in lower_prompt or "cloud run" in lower_prompt or "cloud" in lower_prompt or "google workspace" in lower_prompt else "local",
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

    raw_prompt = heuristic["raw_prompt"]
    llm_modules = _supported_llm_items(llm.get("functional_modules"), raw_prompt)
    llm_roles = _supported_llm_items(llm.get("user_roles"), raw_prompt)
    modules = _filter_modules_by_prompt_context(_unique(llm_modules), raw_prompt) if llm_modules else []
    heuristic_modules = _filter_modules_by_prompt_context(_unique(heuristic["functional_modules"]), raw_prompt)
    if _is_sparse_module_set(modules) and heuristic_modules:
        modules = _unique([*modules, *heuristic_modules])

    roles = _filter_roles_by_prompt_context(_unique(llm_roles), raw_prompt) if llm_roles else []
    heuristic_roles = _filter_roles_by_prompt_context(_unique(heuristic["user_roles"]), raw_prompt)
    if not roles or (set(roles) <= {"usuario", "cliente"} and any(role not in {"usuario", "cliente"} for role in heuristic_roles)):
        roles = _filter_roles_by_prompt_context(_unique(heuristic["user_roles"]), raw_prompt)

    return {
        "project_type": project_type,
        "functional_modules": modules,
        "user_roles": roles,
        "needs_auth": bool(llm.get("needs_auth", heuristic["needs_auth"])) or heuristic["needs_auth"],
        "needs_database": bool(llm.get("needs_database", heuristic["needs_database"])) or heuristic["needs_database"],
        "needs_deployment": bool(llm.get("needs_deployment", heuristic["needs_deployment"])) or heuristic["needs_deployment"],
        "needs_docker": bool(llm.get("needs_docker", heuristic["needs_docker"])) or heuristic["needs_docker"],
        "cloud_target": _normalize_cloud(llm.get("cloud_target"), raw_prompt) if llm.get("cloud_target") else heuristic["cloud_target"],
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


def _has_business_context(lower_prompt: str, terms: list[str], context_terms: list[str]) -> bool:
    for term in terms:
        for match in re.finditer(rf"\b{re.escape(term)}\b", lower_prompt):
            window = lower_prompt[max(0, match.start() - 160) : match.end() + 160]
            if any(context in window for context in context_terms):
                return True
    return False


def _supported_llm_items(value: Any, prompt: str) -> list[str]:
    if not isinstance(value, list):
        return _as_list(value)

    supported: list[str] = []
    lower_prompt = prompt.lower()
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("module") or item.get("role") or "").strip().lower()
            evidence = str(item.get("evidence") or item.get("justification") or "").strip().lower()
            confidence = _safe_float(item.get("confidence"), default=0.75)
            if not name:
                continue
            if _looks_like_delivery_activity(name) or _looks_like_delivery_activity(evidence):
                continue
            if _looks_like_contract_party(name):
                continue
            if confidence < 0.35:
                continue
            if evidence and not _evidence_supported(evidence, lower_prompt):
                continue
            supported.append(name)
            continue

        if isinstance(item, str) and item.strip():
            item_name = item.strip().lower()
            if not _looks_like_delivery_activity(item_name) and not _looks_like_contract_party(item_name):
                supported.append(item_name)

    return supported


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _evidence_supported(evidence: str, lower_prompt: str) -> bool:
    if evidence in lower_prompt:
        return True
    tokens = [
        token
        for token in re.findall(r"[a-záéíóúñ0-9]{4,}", evidence.lower())
        if token not in {"para", "como", "esta", "este", "desde", "donde", "cada", "debe", "deben"}
    ]
    if not tokens:
        return False
    matches = sum(1 for token in tokens if token in lower_prompt)
    return matches / len(tokens) >= 0.5


def _looks_like_delivery_activity(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False

    delivery_patterns = [
        "definir casos de uso",
        "criterios de valor",
        "gate review",
        "provision de accesos",
        "provisión de accesos",
        "apis e interfaces",
        "diseño funcional",
        "diseno funcional",
        "diseño técnico",
        "diseno tecnico",
        "diseño de prompts",
        "diseno de prompts",
        "plantillas, skills",
        "preparar datasets",
        "preparar dataset",
        "implementacion y pruebas",
        "implementación y pruebas",
        "validacion human",
        "validación human",
        "promocion y habilitacion",
        "promoción y habilitación",
        "habilitación a producción",
        "habilitacion a produccion",
        "matriz raci",
        "roles y responsabilidades",
    ]
    if any(pattern in normalized for pattern in delivery_patterns):
        return True

    starts_like_task = re.match(
        r"^(definir|proveer|provisionar|preparar|implementar|validar|promover|habilitar|diseñar|disenar)\b",
        normalized,
    )
    return bool(starts_like_task and len(normalized.split()) >= 4)


def _looks_like_contract_party(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False

    company_terms = [
        " s.a",
        " spa",
        " ltda",
        " limitada",
        " inc",
        " llc",
        " group",
        " compañía",
        " compania",
        " empresa",
    ]
    known_parties = [
        "latam airlines",
        "latam airlines group",
        "ibm chile",
        "ibm chile spa",
        "ibm spa",
        "equipo ibm",
        "ibm delivery",
        "equipo ibm delivery",
    ]
    if any(party in normalized for party in known_parties):
        return True
    return any(term in normalized for term in company_terms)


def _filter_modules_by_prompt_context(modules: list[str], prompt: str) -> list[str]:
    lower_prompt = prompt.lower()
    filtered = [module for module in modules if not _looks_like_delivery_activity(module)]

    if "reservas" in filtered and not _has_business_context(lower_prompt, ["reserva", "reservas"], ["agenda", "calendario", "cita", "booking"]):
        filtered.remove("reservas")
    if "pagos" in filtered and not _has_business_context(lower_prompt, ["pago", "pagos", "cobro", "cobros"], ["checkout", "facturacion", "facturación", "transaccion", "transacción"]):
        filtered.remove("pagos")

    return filtered


def _is_sparse_module_set(modules: list[str]) -> bool:
    meaningful = [
        module
        for module in modules
        if module not in {"digital-workers", "agente", "documentos", "dashboard"}
    ]
    return len(meaningful) < 2


def _filter_roles_by_prompt_context(roles: list[str], prompt: str) -> list[str]:
    lower_prompt = prompt.lower()
    filtered = [
        role
        for role in roles
        if not _looks_like_delivery_activity(role) and not _looks_like_contract_party(role)
    ]
    has_specific_roles = any(role not in {"usuario", "cliente"} for role in filtered)
    if has_specific_roles and len(filtered) > 1:
        filtered = [role for role in filtered if role != "usuario"]
    return filtered


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


def _curate_functional_modules(values: list[str]) -> list[str]:
    curated: list[str] = []
    mappings = [
        (("reserva", "booking"), "reservas"),
        (("calendario", "agenda", "reunion", "reunión", "meeting", "minuta"), "reuniones"),
        (("digital-worker", "digital workers", "digital worker"), "digital-workers"),
        (("skill", "task", "skills-tasks"), "capacidades-automatizadas"),
        (("orquest", "workflow"), "orquestacion"),
        (("human-in-the-loop", "aprobacion", "aprobación"), "human-in-the-loop"),
        (("cuestionario", "questionnaire", "due-diligence", "due diligence"), "cuestionarios"),
        (("regulacion", "regulación", "regulatory", "normativ"), "regulaciones"),
        (("cumplimiento", "compliance"), "cumplimiento"),
        (("crisis", "table-top", "table top"), "gestion-crisis"),
        (("ciberseguridad", "cybersecurity", "cyber"), "ciberseguridad"),
        (("dashboard", "kpi", "tablero"), "dashboard"),
        (("control", "nist", "iso", "pci-dss", "pci dss"), "controles"),
        (("okr",), "okrs"),
        (("onboarding",), "onboarding"),
        (("ticket", "jira"), "tickets"),
        (("integracion", "integración", "api", "google workspace", "gdrive", "gmail"), "integraciones"),
        (("admin", "administr", "gobierno"), "administracion"),
        (("paciente",), "pacientes"),
        (("psicologo", "psicólogo", "profesional", "terapeuta"), "psicologos"),
        (("usuario", "perfil", "cuenta"), "usuarios"),
        (("plan", "suscrip", "billing"), "suscripciones"),
        (("report", "analit", "analytics"), "reportes"),
        (("notific", "alerta"), "notificaciones"),
        (("document", "archivo", "pdf"), "documentos"),
        (("pago", "cobro"), "pagos"),
        (("agente", "chatbot", "asistente", "copilot", "ia"), "agente"),
    ]

    for raw_value in values:
        normalized = str(raw_value or "").strip().lower()
        if not normalized or _looks_like_delivery_activity(normalized) or _looks_like_contract_party(normalized):
            continue

        matched = False
        for keywords, label in mappings:
            if any(keyword in normalized for keyword in keywords):
                matched = True
                if label not in curated:
                    curated.append(label)
                break

        if not matched:
            slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
            if slug and slug not in curated:
                curated.append("-".join(slug.split("-")[:3]))

    return curated[:12] or ["operaciones"]


def _curate_user_roles(values: list[str]) -> list[str]:
    curated: list[str] = []
    mappings = [
        (("admin", "administr"), "administrador"),
        (("operador", "digital worker"), "operador-digital-worker"),
        (("aprobador", "usuario autorizado", "human-in-the-loop"), "aprobador-cliente"),
        (("cumplimiento", "compliance"), "analista-cumplimiento"),
        (("ciberseguridad", "cybersecurity"), "equipo-ciberseguridad"),
        (("auditor", "control assurance"), "auditor"),
        (("paciente",), "paciente"),
        (("psicologo", "psicólogo", "profesional", "terapeuta"), "psicologo"),
        (("usuario", "cliente"), "usuario"),
    ]

    for raw_value in values:
        normalized = str(raw_value or "").strip().lower()
        if not normalized or _looks_like_delivery_activity(normalized) or _looks_like_contract_party(normalized):
            continue

        matched = False
        for keywords, label in mappings:
            if any(keyword in normalized for keyword in keywords):
                matched = True
                if label not in curated:
                    curated.append(label)
                break

        if not matched and normalized not in curated:
            curated.append(normalized)

    return curated[:8]


def _derive_project_profile(prompt: str, modules: list[str]) -> str:
    lower_prompt = prompt.lower()
    ai_modules = {"agente", "digital-workers", "orquestacion", "skills-tasks", "capacidades-automatizadas", "human-in-the-loop"}
    if any(keyword in lower_prompt for keyword in ["agente", "chatbot", "asistente", "langgraph", "copilot", "ia generativa"]) or any(module in ai_modules for module in modules):
        return "ai"
    if any(keyword in lower_prompt for keyword in ["microservicio", "microservicios", "event-driven", "worker", "cola"]):
        return "microservices"
    return "standard"


def _derive_service_layout(prompt: str, project_profile: str, project_type: str) -> tuple[bool, int]:
    if project_type == "web":
        return False, 0
    lower_prompt = prompt.lower()
    if project_profile == "microservices":
        return True, 2
    worker_count = _infer_digital_worker_count(prompt)
    if worker_count:
        return True, min(worker_count, 3)
    if any(keyword in lower_prompt for keyword in ["servicio adicional", "servicios adicionales", "worker", "jobs", "colas"]):
        return True, 1
    return False, 0


def _infer_digital_worker_count(prompt: str) -> int:
    lower_prompt = prompt.lower()
    if "digital worker" not in lower_prompt and "digital workers" not in lower_prompt:
        return 0
    numbered = len(re.findall(r"\b\d+\.\s+[A-ZÁÉÍÓÚÑ][^\n]{3,80}", prompt))
    bullets = len(re.findall(r"[●•-]\s+[A-ZÁÉÍÓÚÑ][^\n]{3,100}", prompt))
    explicit = re.search(r"\b(?:tres|3)\s+digital\s+workers?\b", lower_prompt)
    if explicit:
        return 3
    return max(1, min(3, numbered or bullets))


def _derive_navigation_sections(modules: list[str], project_profile: str) -> list[str]:
    section_aliases = {
        "dashboard": "dashboard-ejecutivo",
        "administracion": "administracion-avanzada",
        "usuarios": "gestion-usuarios",
    }
    sections = [section_aliases.get(module, module) for module in modules]
    if project_profile == "ai" and "agente" not in sections and "digital-workers" not in sections:
        sections.insert(0, "agente")
    return _unique(sections)[:12]


def _derive_experience_mode(roles: list[str]) -> str:
    normalized_roles = {str(role).strip().lower() for role in roles if str(role).strip()}
    if normalized_roles and normalized_roles - {"admin", "administrador"}:
        return "user"
    return "admin"
