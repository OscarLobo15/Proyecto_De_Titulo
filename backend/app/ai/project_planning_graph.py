"""
IBM Method Workspace – Intelligent Project Planning Graph

Produces a complete IBM Consulting delivery plan from a plain-language project
description.  The graph calls the LLM three times with rich IBM Method Workspace
context so the model can reason autonomously – no hard-coded rules per project type.

Nodes:
  receive_plan_request
  → generate_method_and_team        [LLM call 1]
  → generate_user_stories           [LLM call 2]
  → generate_architecture_decisions [LLM call 3]
  → compute_cost_estimate           [pure Python]
  → assemble_plan                   [pure Python]
  → END
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.models import (
    ADR,
    CloudServiceLine,
    CostEstimate,
    CostRoleBreakdown,
    IBMProjectPlan,
    IBMRole,
    UserStory,
    WBSPhase,
    WBSTask,
)
from app.services.ai_client import RemoteLLMClient

logger = logging.getLogger(__name__)

DEFAULT_MONTHLY_RATE_CLP = 5_000_000
MIN_REALISTIC_MONTHLY_RATE_CLP = 2_500_000

ROLE_RATE_TABLE_CLP = {
    "business sales & delivery leader: associate partner": 11_000_000,
    "associate partner": 11_000_000,
    "application architect: hybrid cloud": 8_500_000,
    "solution architect": 8_500_000,
    "architect": 8_500_000,
    "automation architect": 7_500_000,
    "ai architect": 7_500_000,
    "client project manager": 7_000_000,
    "project manager": 7_000_000,
    "cloud build platform architect": 6_500_000,
    "application developer: devops": 6_000_000,
    "devops lead": 6_000_000,
    "agile coach": 5_500_000,
    "application developer": 5_000_000,
    "developer": 5_000_000,
    "business analyst": 5_000_000,
    "application architect: quality engineering": 4_500_000,
    "qa engineer": 4_500_000,
    "ux designer": 4_500_000,
    "data architect": 7_000_000,
    "cybersecurity architect": 7_500_000,
}

# Cloud infrastructure reference pricing (CLP/month, conservative Chile market estimates)
# Each entry: [monthly_cost_clp, one_time_setup_cost_clp]
CLOUD_PRICING_CLP: dict[str, dict[str, list[int]]] = {
    "gcp": {
        "Cloud Run / GKE (compute)":        [480_000,  350_000],
        "Cloud SQL (base de datos)":         [320_000,  200_000],
        "Cloud Storage (almacenamiento)":    [80_000,   50_000],
        "Firebase / Identity Platform (auth)": [60_000, 30_000],
        "Cloud Load Balancing + CDN":        [120_000,  80_000],
        "Cloud Monitoring & Logging":        [80_000,   0],
        "Vertex AI (si aplica IA)":          [400_000,  120_000],
    },
    "aws": {
        "ECS / EKS (compute)":              [520_000,  400_000],
        "RDS (base de datos)":              [340_000,  200_000],
        "S3 (almacenamiento)":              [75_000,   40_000],
        "Cognito (auth)":                   [55_000,   30_000],
        "ALB + CloudFront (CDN)":           [130_000,  80_000],
        "CloudWatch (monitoreo)":            [90_000,   0],
        "SageMaker (si aplica IA)":         [450_000,  150_000],
    },
    "azure": {
        "AKS / Container Apps (compute)":   [500_000,  380_000],
        "Azure SQL / CosmosDB":             [360_000,  220_000],
        "Blob Storage (almacenamiento)":    [78_000,   40_000],
        "Azure AD B2C (auth)":              [65_000,   35_000],
        "Azure Front Door + CDN":           [140_000,  90_000],
        "Azure Monitor (monitoreo)":        [85_000,   0],
        "Azure OpenAI Service (si aplica)": [480_000,  130_000],
    },
    "local": {},
}

# Which services to include per project profile
_CLOUD_PROFILE_SERVICES: dict[str, list[str]] = {
    "standard":      ["compute", "base de datos", "almacenamiento", "auth", "CDN", "monitoreo"],
    "ai":            ["compute", "base de datos", "almacenamiento", "auth", "CDN", "monitoreo", "IA"],
    "microservices": ["compute", "base de datos", "almacenamiento", "CDN", "monitoreo"],
    "api-only":      ["compute", "base de datos", "monitoreo"],
}


def _select_cloud_services(provider: str, profile: str, has_ai: bool) -> list[dict]:
    """Pick the relevant cloud service lines for the given provider + project profile."""
    provider_key = provider.lower() if provider else "local"
    if provider_key not in CLOUD_PRICING_CLP or not CLOUD_PRICING_CLP[provider_key]:
        return []

    keywords = _CLOUD_PROFILE_SERVICES.get(profile, _CLOUD_PROFILE_SERVICES["standard"])
    if has_ai and "IA" not in keywords:
        keywords = keywords + ["IA"]

    selected = []
    for service_name, (monthly, setup) in CLOUD_PRICING_CLP[provider_key].items():
        # Include service if any of its keywords match what this profile needs
        if any(kw.lower() in service_name.lower() for kw in keywords):
            selected.append({
                "service": service_name,
                "monthly_cost_clp": monthly,
                "setup_cost_clp": setup,
                "notes": "",
            })
    return selected


SPANISH_TERM_MAP = {
    "Project Manager": "Jefe de Proyecto",
    "Solution Architect": "Arquitecto de Solución",
    "Business Analyst": "Analista de Negocio",
    "Developer": "Desarrollador",
    "Application Developer": "Desarrollador de Aplicaciones",
    "DevOps Lead": "Líder DevOps",
    "QA Engineer": "Especialista QA",
    "AI Architect": "Arquitecto IA",
    "Automation Architect": "Arquitecto de Automatización",
    "UX Designer": "Diseñador UX",
    "Data Architect": "Arquitecto de Datos",
    "Cybersecurity Architect": "Arquitecto de Ciberseguridad",
    "All": "Todo el proyecto",
    "Iteration 0": "Iteración 0",
    "Iterations": "Iteraciones",
    "Iterations 1-n": "Iteraciones 1-n",
    "Close": "Cierre",
    "AI Strategy": "Estrategia IA",
    "AI Build": "Construcción IA",
    "AI Design": "Diseño IA",
    "AI Operationalize": "Operacionalización IA",
    "Architecture Overview": "Resumen de Arquitectura",
    "Architecture Overview Document": "Documento de Resumen de Arquitectura",
    "Development Environment": "Entorno de Desarrollo",
    "Working Software": "Software Funcional",
    "Sprint Reviews": "Revisiones de Sprint",
    "Test Reports": "Reportes de Pruebas",
    "Deployed Application": "Aplicación Desplegada",
    "User Documentation": "Documentación de Usuario",
    "Implementation Project Plan": "Plan de Implementación del Proyecto",
    "Acceptance Test Plan": "Plan de Pruebas de Aceptación",
    "Configuration Management": "Gestión de Configuración",
    "Change Management (Agile and Traditional)": "Gestión del Cambio (Ágil y Tradicional)",
    "AI Use Cases List": "Listado de Casos de Uso IA",
    "LLM Selection Report": "Informe de Selección de LLM",
    "AI Agent v1": "Agente IA v1",
    "Integration Tests": "Pruebas de Integración",
    "Hybrid Cloud & Data": "Nube Híbrida y Datos",
    "Application Operations": "Operaciones de Aplicaciones",
    "Business Applications": "Aplicaciones de Negocio",
    "Business Operations": "Operaciones de Negocio",
    "Cybersecurity": "Ciberseguridad",
    "Strategy & Transformation": "Estrategia y Transformación",
    "Delivery": "Entrega",
    "Solutioning": "Definición de solución",
    "Dashboard": "Tablero",
    "Setup": "Preparación",
    "features": "funcionalidades",
    "scope": "alcance",
    "stakeholders": "interesados",
    "Stakeholders": "Interesados",
    "sign-offs": "aprobaciones",
    "Sprint planning": "Planificación de sprint",
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ProjectPlanState(TypedDict, total=False):
    description: str
    project_name: str
    selected_architecture: dict[str, Any]
    method_and_team: dict[str, Any]       # output of LLM call 1
    raw_user_stories: list[dict]           # output of LLM call 2
    raw_adrs: list[dict]                   # output of LLM call 3
    plan: IBMProjectPlan


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_project_planning_graph(llm_client: Optional[RemoteLLMClient] = None) -> Any:
    from app.config import settings
    client = llm_client or RemoteLLMClient(timeout_seconds=settings.ai_project_generation_timeout_seconds)

    graph = StateGraph(ProjectPlanState)
    graph.add_node("receive_plan_request", receive_plan_request)
    graph.add_node("generate_method_and_team", lambda s: generate_method_and_team(s, client))
    graph.add_node("generate_plan_artifacts", lambda s: generate_plan_artifacts(s, client))
    graph.add_node("compute_cost_estimate", compute_cost_estimate)
    graph.add_node("assemble_plan", assemble_plan)

    graph.set_entry_point("receive_plan_request")
    graph.add_edge("receive_plan_request", "generate_method_and_team")
    graph.add_edge("generate_method_and_team", "generate_plan_artifacts")
    graph.add_edge("generate_plan_artifacts", "compute_cost_estimate")
    graph.add_edge("compute_cost_estimate", "assemble_plan")
    graph.add_edge("assemble_plan", END)
    return graph.compile()


def _extract_name_from_text(text: str) -> Optional[str]:
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


def plan_project_with_ai(
    description: str,
    project_name: Optional[str] = None,
    selected_architecture: Optional[dict] = None,
    llm_client: Optional[RemoteLLMClient] = None,
) -> tuple[str, IBMProjectPlan]:
    client = llm_client or RemoteLLMClient()
    resolved_name = _resolve_project_name(description, project_name, client)
    logger.info("Starting IBM project planning graph for: %s", resolved_name)
    app = build_project_planning_graph(client)
    final_state = app.invoke({
        "description": description.strip(),
        "project_name": resolved_name,
        "selected_architecture": selected_architecture or {},
    })
    plan = final_state.get("plan")
    if not isinstance(plan, IBMProjectPlan):
        raise RuntimeError("El grafo de planificación IBM no produjo un plan válido.")
    return resolved_name, plan


# ---------------------------------------------------------------------------
# Node: receive_plan_request
# ---------------------------------------------------------------------------

def receive_plan_request(state: ProjectPlanState) -> ProjectPlanState:
    logger.info("IBM planning node: receive_plan_request")
    return {
        "description": state["description"].strip(),
        "project_name": state.get("project_name", "proyecto-ibm").strip().lower().replace(" ", "-"),
        "selected_architecture": state.get("selected_architecture") or {},
    }


# ---------------------------------------------------------------------------
# Node: generate_method_and_team  [LLM call 1]
# ---------------------------------------------------------------------------

def generate_method_and_team(state: ProjectPlanState, llm_client: RemoteLLMClient) -> ProjectPlanState:
    logger.info("IBM planning node: generate_method_and_team")
    prompt = _build_method_and_team_prompt(state)
    raw = llm_client.generate(prompt)
    parsed = _safe_extract_json(raw)
    if not parsed:
        logger.warning("LLM returned unparseable response for method_and_team; using fallback")
        parsed = _fallback_method_and_team(state)
    elif _mentions_unrequested_chatbot(parsed, state["description"]):
        logger.warning("LLM method_and_team invented chatbot scope; using architecture-aware fallback")
        parsed = _fallback_method_and_team(state)
    return {"method_and_team": parsed}


def _build_method_and_team_prompt(state: ProjectPlanState) -> str:
    arch = state.get("selected_architecture") or {}
    arch_summary = json.dumps({k: v for k, v in arch.items() if k in (
        "project_type", "frontend", "backend", "database", "auth",
        "cloud", "project_profile", "include_langgraph", "include_services",
        "service_count", "functional_modules", "navigation_sections", "roles",
        "microservices", "integrations",
    )}, ensure_ascii=False) if arch else "{}"
    planning_context = _planning_context_from_arch(arch)

    return f"""
Eres un Arquitecto Senior de Soluciones de IBM Consulting con acceso completo al catálogo IBM Method Workspace.
Tu tarea es producir un plan completo de entrega para un nuevo engagement.
Responde SOLO con JSON válido. No uses markdown ni explicaciones fuera del JSON.

## IDIOMA Y MONEDA
- Toda la salida visible para usuario debe estar en español: justificaciones, fases, objetivos, tareas, entregables, riesgos, ADRs, historias de usuario y notas.
- Puedes conservar nombres oficiales de métodos IBM y nombres técnicos propios como React, FastAPI, LangGraph, IBM Method Workspace o ADR.
- No escribas frases en inglés como "Working Software", "Sprint Reviews", "Accepted", "As a", "I want" ni "so that"; tradúcelas al español.
- Todos los montos deben estar en CLP mensual. Nunca uses valores por hora, por día ni valores menores a 2_500_000 CLP/mes.

## IBM METHOD WORKSPACE — COMPLETE METHODS CATALOGUE (37 methods, 7 service lines)

### CROSS SERVICE LINE METHODS (CSLM)
1. IBM Services Mosaic Method — large multi-offering IBM engagements combining multiple service lines
2. Solutioning — pre-sales technical solutioning and RFP response
3. Team Solution Design — complex multi-discipline solution workshops, design sprints
4. Worldwide Program Management Method - WWPgMM — program-level governance, benefits realization tracking
5. Worldwide Project Management Method - WWPMM Agile — multi-team agile programs, PMO, stakeholder governance
   Phases: Initiate → Plan → Execute → Control → Close
6. Worldwide Project Management Method - WWPMM Traditional — traditional waterfall program management

### APPLICATION OPERATIONS (AOP)
7. Application IMPACT - Maintenance — steady-state application maintenance and support engagements
8. Application IMPACT - Quality Engineering — QE-focused transformation, test maturity, automation CoE
9. Application IMPACT - Transition — application transition and knowledge transfer from incumbent vendor
10. IBM DevSecOps and AIOps — CI/CD transformation, platform engineering, DevOps maturity, AIOps
    Phases: Assess (2w) → Design (2w) → Build (6-10w) → Operate (ongoing)
11. Platform Services Delivery for Hybrid Cloud — ongoing hybrid cloud platform operations and SRE

### BUSINESS APPLICATIONS (BAP)
12. Enterprise SAP Transformation — SAP S/4HANA transformation, RISE with SAP
    Phases: Prepare → Explore → Realize → Deploy → Run
13. IBM Ascend for SAP Application Development — custom development on SAP platform
    Phases: Initiate → Design → Build → Test → Deploy
14. IBM Ascend Powered by SAP Activate SuccessFactors — SAP SuccessFactors HCM implementation
    Phases: Prepare → Explore → Realize → Deploy → Run
15. IBM Oracle On-Premise Application Implementation and Upgrade — Oracle EBS, JDE on-premise
    Phases: Project Initiation → Analysis → Design → Build → Test → Deploy
16. IBM Oracle Rapid Move for Cloud — Oracle cloud migration (OCI, ERP Cloud)
    Phases: Assess → Plan → Migrate → Validate → Operate
17. IBM Salesforce Engagement — Salesforce CRM/Sales Cloud/Service Cloud implementations
    Phases: Discover → Define → Design → Build → Test → Launch → Optimize
18. Marketing & Experience Transformation with Adobe — Adobe Experience Platform, AEM, Campaign
    Phases: Strategy → Design → Build → Launch → Optimize
19. Workday — Workday HCM, Finance, Payroll implementation
    Phases: Plan → Architect → Configure → Test → Deploy → Operate

### BUSINESS OPERATIONS (BOP)
20. BPO Transition — business process outsourcing transition and stabilization
    Phases: Mobilize → Transition → Stabilize → Optimize
21. Content Intelligence — intelligent document processing, content management
    Phases: Assess → Design → Build → Deploy → Operate
22. Customer Care — contact center transformation, omnichannel, IVR
    Phases: Discover → Design → Implement → Stabilize → Optimize
23. Garage Method for Automation — RPA (UiPath, Automation Anywhere), intelligent automation
    Phases: Discover → Design → Develop → Test → Deploy → Scale
24. Service Transformation — ITSM, ServiceNow, shared services operating model
    Phases: Assess → Design → Build → Transition → Optimize

### CYBERSECURITY (CSS)
25. Cyber Strategy and Risk [NEW] — cyber risk assessment, zero trust strategy, CISO advisory
    Phases: Assess → Strategize → Roadmap → Implement → Monitor
26. Cyber Threat Management — SOC operations, SIEM, threat intelligence, incident response
    Phases: Assess → Design → Deploy → Operate → Optimize
27. CyberDefend — IBM managed security services, 24x7 threat detection
    Phases: Onboard → Baseline → Protect → Detect & Respond → Report

### HYBRID CLOUD & DATA (HCD)
28. AI Integration — LLM integration, AI agents, LangGraph, Watson, cognitive automation, chatbots
    Phases: AI Strategy (2-3w) → AI Design (3-4w) → AI Build (8-12w) → AI Operationalize (3-4w)
29. Agentic Method for Application Migration and Modernization — AI-assisted legacy modernization,
    microservices decomposition, application re-platforming
    Phases: Discovery → Assessment → Treatment Design → Realization → Day-2 Ops
30. Application Development - Agile (AD-Agile) — custom web/fullstack/API/SaaS development
    Lifecycle: Start → Iteration 0 (2-3w) → Iterations 1-n (2-week sprints: Planning, Design & Build,
    Confirm/Deploy) → Close. Disciplines: Management, Technical Governance, Business & Strategy,
    Architecture, Requirements, UX, Design & Development, Test, Environment & Infrastructure, Deploy
31. Application Development - Waterfall (AD-Waterfall) — fixed-scope enterprise apps, ERP, regulatory
    Phases: Start → Solution Outline → Macro Design → Micro Design → Build → Deploy → Close
32. Application Move and Modernization — cloud lift-and-shift, container migration, re-hosting
33. Data Governance [NEW] — data catalog, master data management, data quality, GDPR/compliance
    Phases: Assess → Design → Implement → Operate
34. Data Transformation — data pipelines, ETL/ELT, dbt, Spark, data warehouse modernization
    Phases: Discovery → Architecture → Build → Validate → Operate
35. IBM Ascend for Microsoft Business Solution Implementation or Upgrade — Microsoft Dynamics 365
36. IBM Ascend for Microsoft SaaS Delivery — Microsoft SaaS solutions (Power Platform, M365)
37. IBM Garage Method for Cloud - Advise — cloud strategy, digital transformation advisory, innovation
    Phases: Discover (2w) → Explore (3w) → Experiment (4-8w) → Scale (ongoing)
38. IBM Oracle Rapid Move for Cloud Infrastructure — Oracle workloads to OCI infrastructure
39. Scaled Data Science — ML/AI model development, MLOps, Python/Jupyter/sklearn/PyTorch at scale

### STRATEGY & TRANSFORMATION (STR)
40. Business Process Management — BPM/process mining, Celonis, enterprise process redesign
    Phases: Discover → Analyze → Redesign → Implement → Monitor
41. Commerce — e-commerce platforms (Salesforce Commerce, Adobe Commerce/Magento, HCL Commerce)
    Phases: Strategy → Design → Build → Launch → Optimize
42. Connected Solutions — IoT, edge computing, device connectivity solutions
    Phases: Envision → Design → Pilot → Scale → Operate
43. Experience Strategy & Design — UX research, service design, design systems, prototyping
    Phases: Research → Synthesis → Concept → Prototype → Validate → Implement
44. Finance Transformation Advisory — CFO advisory, finance operating model, FP&A modernization
    Phases: Assess → Design → Roadmap → Implement → Sustain
45. IBM Change — organizational change management, communication, training for digital transformations
    Phases: Assess → Plan → Execute → Embed → Sustain
46. Maximo Method — IBM Maximo EAM implementation and upgrade
    Phases: Initiate → Configure → Integrate → Test → Deploy → Support
47. Package Implementation — generic enterprise package implementation (non-SAP/Oracle/Salesforce)
    Phases: Initiate → Analyze → Design → Build → Test → Deploy
48. Supply Chain and Procurement Strategy [NEW] — supply chain resilience, procurement transformation
    Phases: Assess → Strategize → Design → Implement → Monitor
49. Talent Transformation Consult to Operate — HR transformation, talent strategy, learning
    Phases: Diagnose → Design → Pilot → Scale → Operate

## IBM METHOD WORKSPACE — ADOPTION JOURNEYS
- "Delivery Journey": Apply when the engagement is an active delivery project for a client.
  Guide: focus on repeatable method reuse, asset selection, sprint-by-sprint governance.
- "Solutioning Journey": Apply when the engagement is in pre-sales or proposal phase.
  Guide: focus on IBM method references in proposals, effort estimation with SEP, win themes.

## IBM METHOD WORKSPACE — ROLES (use EXACT role names from this list):
- "Client Project Manager" — project delivery, WBS, financials, client governance
- "Application Architect: Hybrid Cloud" — full-stack hybrid cloud architecture and patterns
- "Business Analyst" — requirements, user stories, UAT, functional specs
- "Application Developer: DevOps" — CI/CD, Dockerfile, IaC, environment automation
- "Application Developer" — fullstack feature development, unit tests, code reviews
- "Automation Architect" — AI/ML design, LangGraph agent flows, Watson, MLOps
- "Agile Coach" — Scrum facilitation, ceremonies, velocity, retrospectives
- "Application Architect: Quality Engineering" — test strategy, QA automation frameworks
- "Business Sales & Delivery Leader: Associate Partner" — senior oversight, escalation, C-level
- "Application Consultant - DevOps" — DevOps toolchain, methodology adoption
- "Cloud Build Platform Architect" — Kubernetes, cloud infrastructure, SRE
- "Application Architect - Digital Modernization" — legacy analysis, modernization roadmap
- "Business Transformation Consultant" — org change, digital transformation strategy
- "Data Architect" — data modeling, governance, pipeline design
- "Cybersecurity Architect" — security architecture, zero trust, threat modeling
- "UX Designer" — user research, prototyping, design systems, accessibility

## IBM CONSULTING CHILE — APPROXIMATE MONTHLY RATES (CLP, 2025):
- "Business Sales & Delivery Leader: Associate Partner": 11_000_000
- "Application Architect: Hybrid Cloud" (Senior): 8_500_000
- "Automation Architect" / AI Architect: 7_500_000
- "Client Project Manager" (Senior): 7_000_000
- "Cloud Build Platform Architect": 6_500_000
- "Application Developer: DevOps" (Senior): 6_000_000
- "Agile Coach": 5_500_000
- "Application Developer" (Senior) / "Business Analyst" (Senior): 5_000_000
- "Application Architect: Quality Engineering": 4_500_000
- "Application Developer" (Mid) / "Business Analyst" (Mid): 3_500_000
- "Application Developer" (Junior): 2_500_000
- IMPORTANT: These are monthly role costs in Chilean pesos. Do not output 300_000, 500_000, hourly values, daily values, UF values or USD values.

## PROJECT TO PLAN:
Name: {state["project_name"]}
Description: {state["description"]}
Technical architecture selected: {arch_summary}
Detected delivery scope: {planning_context}

## TASK:
Using the complete IBM Method Workspace knowledge above, select the single best-fit method
and produce the full delivery plan. The method MUST be justified by domain and nature —
do not default to AD-Agile unless it genuinely fits a custom app dev engagement.

## FIDELITY RULES — CRITICAL:
- Treat the description and Detected delivery scope as the source of truth. Do not replace it with a generic chatbot, generic task manager, CRM, reservations, payments, or CRUD-user application unless those capabilities are explicitly present.
- If the project refers to Digital Workers, skills/tasks, human-in-the-loop, orchestration, meetings, documents, OKRs, GRC, governance, risk or compliance, plan for those capabilities directly. Do not summarize them as "chatbot" unless the document explicitly says chatbot.
- Contract boilerplate, signatures, prices, legal clauses and company names are context, not product modules or end-user roles.
- When services are detected, the WBS, roles, risks and user stories must cover navigation/operation across those services, not a single monolithic screen.
- Every phase, risk and deliverable must be traceable to at least one detected capability, role, service or technology in the project context.

## METHOD SELECTION — PRIORITY RULES (apply in order, first match wins):

### PRIORITY 1 — Specific enterprise packages (always wins when named explicitly):
- SAP S/4HANA, SuccessFactors, RISE with SAP → Enterprise SAP Transformation (BAP)
- Salesforce Sales/Service/Marketing Cloud → IBM Salesforce Engagement (BAP)
- Workday HCM, Finance, Payroll → Workday (BAP)
- Oracle EBS, JDE on-premise → IBM Oracle On-Premise (BAP)
- Oracle Cloud / OCI migration → IBM Oracle Rapid Move for Cloud (BAP)
- Microsoft Dynamics 365 → IBM Ascend for Microsoft (HCD)
- Adobe Experience Platform, AEM, Campaign → Marketing & Experience Transformation (BAP)
- IBM Maximo EAM → Maximo Method (STR)
- ServiceNow, ITSM, shared services → Service Transformation (BOP)
- UiPath, Automation Anywhere, RPA → Garage Method for Automation (BOP)

### PRIORITY 2 — Specialized domains (wins when the domain is the core focus):
- SOC, SIEM, threat intelligence, incident response → Cyber Threat Management (CSS)
- CISO advisory, zero trust strategy, cyber risk assessment → Cyber Strategy and Risk (CSS)
- ETL, dbt, Spark, data warehouse modernization (data engineering is the CORE) → Data Transformation (HCD)
- Data catalog, master data, GDPR, data governance (governance is the CORE) → Data Governance (HCD)
- ML models, Jupyter, PyTorch, scikit-learn, MLOps (model development is the CORE) → Scaled Data Science (HCD)
- Legacy app modernization WITH AI assistance, microservices decomposition → Agentic Method (HCD)
- Pure CI/CD transformation, DevOps maturity, platform engineering as the core → IBM DevSecOps and AIOps (AOP)
- UX research-led, service design, design system as the core deliverable → Experience Strategy & Design (STR)
- Organizational change, OCM, training as the core deliverable → IBM Change (STR)
- Cloud strategy advisory, innovation workshop, tech strategy (no build) → IBM Garage Method (HCD)
- Multi-team program (3+ parallel workstreams), PMO governance → WWPMM Agile (CSLM)
- Steady-state application support, maintenance SLAs → Application IMPACT - Maintenance (AOP)

### PRIORITY 3 — AI/LLM signal (wins for AI-CORE projects):
- The project's PRIMARY value/product is AI: chatbot, AI agent, LLM integration → AI Integration (HCD)
- IMPORTANT DISTINCTION: If a web/API/fullstack app USES LangGraph or AI as an internal
  orchestration TOOL (not as the product itself), this is still AD-Agile. AI Integration
  only applies when the AI capability IS the product or main deliverable.
  Example: "Plataforma que usa LangGraph para generar proyectos" → AD-Agile (LangGraph is a tool)
  Example: "Chatbot empresarial con LLM y memoria" → AI Integration (el chatbot ES el producto)

### PRIORITY 4 — Default application development:
- Custom web app, fullstack (React/FastAPI, Node, etc.), SaaS, API product → AD-Agile (HCD)
- Fixed-scope delivery, regulatory, ERP custom development → AD-Waterfall (HCD)

## IMPLICIT SIGNAL DETECTION:
Read between the lines. These signals imply the following methods even if not stated explicitly:
- "reportes", "dashboard analítico", "KPIs" alone → does NOT change method (still AD-Agile/AI)
- "certificación", "normativa", "regulatorio", "SOX", "ISO" → lean toward AD-Waterfall
- "piloto", "innovación", "exploración", "PoC" → lean toward IBM Garage Method
- "modernizar sistema legacy", "migrar monolito" → Agentic Method
- "mejorar calidad de datos", "fuente única de verdad" → Data Governance
- "integrar con SAP" (integration work, not an SAP project) → stays AD-Agile
- "plataforma generadora", "herramienta interna", "automatizar procesos internos" → AD-Agile
  unless RPA tools are mentioned (then Garage Method for Automation)

Additionally, determine the adoption_journey:
- "Delivery" if the project description implies an active delivery engagement
- "Solutioning" if the description implies pre-sales, proposal, or RFP context

Respond with this EXACT JSON contract (no extra keys, no markdown):
{{
  "ibm_recommended_method": "<method name exactly as in the catalogue>",
  "ibm_method_rationale": "<3-5 sentences in Spanish fully justifying method selection. MUST: (1) Name the specific IBM Method Workspace attributes (phases, disciplines, or lifecycle) that align with this engagement's nature. (2) Explain WHY this method was chosen over the 2 most plausible alternatives — name those alternatives explicitly and state the disqualifying reason for each. (3) Reference a concrete project characteristic (tech stack, domain, scope, risk) that seals the choice. Do not write generic sentences — every sentence must be evidence-backed and specific to THIS project.>",
  "service_line": "<primary service line abbreviation and name>",
  "project_overview": "<3-4 sentences describing the project from IBM Consulting perspective: business problem, proposed solution approach, expected outcome, and strategic value for the client. Be concrete and specific to this engagement.>",
  "adoption_journey": "Delivery | Solutioning",
  "tailoring_notes": "<2-3 sentences describing specifically HOW the selected IBM method was adapted for this engagement. Mention: which standard phases were shortened/extended and why; any discipline overlaps; any IBM work products replaced or supplemented; and how the team composition tailors the method's standard resourcing model. Be specific — do not write generalities.>",
  "team_roles": [
    {{
      "role_name": "<SHORT functional name — e.g. 'Project Manager', 'Solution Architect', 'Developer'>",
      "ibm_method_workspace_role": "<exact IBM MW role name from the list above>",
      "seniority": "Senior | Mid | Junior",
      "phase": "<All | specific phase name from the selected method>",
      "dedication_weeks": <integer 1-52>,
      "monthly_rate_clp": <integer from the rate table above; minimum 2_500_000>,
      "justification": "<2-3 sentences in Spanish specific to THIS project. State: (1) the specific deliverable or phase this role owns, (2) WHY this seniority level is required given project complexity, and (3) how this role integrates with another key role in the team.>"
    }}
  ],
  "wbs_phases": [
    {{
      "phase_name": "<phase name for this engagement>",
      "ibm_method_phase": "<EXACT official phase name from the selected IBM method phases listed above>",
      "duration_weeks": <integer>,
      "objectives": ["<specific objective 1>", "<specific objective 2>"],
      "tasks": [
        {{
          "task": "<specific task>",
          "responsible_role": "<MUST match the role_name (short name) from team_roles above>",
          "effort_days": <float>
        }}
      ],
      "deliverables": ["<IBM work product or deliverable 1>", "<deliverable 2>"]
    }}
  ],
  "project_risks": [
    "<Risk 1: Name the specific risk tied to THIS stack or domain. Format: '[Risk category]: [What could go wrong] → Mitigation: [concrete IBM Consulting action to reduce it]'>",
    "<Risk 2 — same format>",
    "<Risk 3 — same format>",
    "<Risk 4 — same format>",
    "<Risk 5 — same format>"
  ],
  "ibm_assets_recommended": [
    "<IBM Method Workspace work product or asset name — be specific, e.g. 'Solution Architecture Document (SAD)', 'Iteration Plan', 'Definition of Ready checklist'>",
    "<asset 2>",
    "<asset 3>",
    "<asset 4>",
    "<asset 5>"
  ]
}}

CONSTRAINTS:
- Output language: Spanish for all user-facing text. Keep only official IBM method names and technology names in their original form.
- monthly_rate_clp must be a realistic monthly CLP cost from the table. Minimum allowed value: 2_500_000.
- team_roles: 5-7 roles minimum. Every project needs PM + Architect + Developer.
  AI projects require Automation Architect. Data projects require Data Architect.
  QE-focused projects require Application Architect: Quality Engineering.
  role_name MUST be a short label (2-4 words) used as the display name in the plan.
- wbs_phases: 3-5 phases using the EXACT phase names from the selected method as listed above.
  Each phase: 3-5 tasks, 2-3 deliverables.
  tasks[].responsible_role MUST exactly match one of the role_name values from team_roles.
- project_risks: EXACTLY 5 risks. Each risk MUST name a specific technology, team pattern, or domain challenge from THIS project and include a concrete mitigation action. No generic project management risks.
- ibm_assets_recommended: 4-6 IBM MW work products. Use official IBM Method Workspace asset names.
""".strip()


# ---------------------------------------------------------------------------
# Node: generate_plan_artifacts  [LLM calls 2 and 3 in parallel]
# ---------------------------------------------------------------------------

def generate_plan_artifacts(state: ProjectPlanState, llm_client: RemoteLLMClient) -> ProjectPlanState:
    logger.info("IBM planning node: generate_plan_artifacts")
    with ThreadPoolExecutor(max_workers=2) as executor:
        stories_future = executor.submit(generate_user_stories, state, llm_client)
        adrs_future = executor.submit(generate_architecture_decisions, state, llm_client)

        stories_update = stories_future.result()
        adrs_update = adrs_future.result()

    return {
        "raw_user_stories": stories_update.get("raw_user_stories", []),
        "raw_adrs": adrs_update.get("raw_adrs", []),
    }


# ---------------------------------------------------------------------------
# Node: generate_user_stories  [LLM call 2]
# ---------------------------------------------------------------------------

def generate_user_stories(state: ProjectPlanState, llm_client: RemoteLLMClient) -> ProjectPlanState:
    logger.info("IBM planning node: generate_user_stories")
    mt = state.get("method_and_team") or {}
    prompt = _build_user_stories_prompt(state, mt)
    raw = llm_client.generate(prompt)
    parsed = _safe_extract_json_array(raw)
    if not parsed:
        logger.warning("LLM returned unparseable response for user_stories; using fallback")
        parsed = _fallback_user_stories(state)
    elif _mentions_unrequested_chatbot(parsed, state["description"]):
        logger.warning("LLM user stories invented chatbot scope; using architecture-aware fallback")
        parsed = _fallback_user_stories(state)
    return {"raw_user_stories": parsed}


def _build_user_stories_prompt(state: ProjectPlanState, mt: dict) -> str:
    roles = [r.get("role_name", "") for r in mt.get("team_roles", [])]
    method = mt.get("ibm_recommended_method", "Application Development - Agile (AD-Agile)")
    arch = state.get("selected_architecture") or {}
    tech_summary = _tech_summary_from_arch(arch, state["description"])
    planning_context = _planning_context_from_arch(arch)

    return f"""
Eres un Analista de Negocio de IBM Consulting aplicando el método {method}.
Tu tarea es generar historias de usuario para un engagement IBM.
Responde SOLO con un arreglo JSON válido. No uses markdown ni explicaciones fuera del JSON.

## IDIOMA
- Toda la salida visible debe estar en español.
- Conserva solo nombres técnicos propios cuando corresponda (React, FastAPI, Firebase, PostgreSQL, etc.).
- Usa "Como", "quiero" y "para" conceptualmente, pero los campos JSON deben mantenerse con los nombres solicitados.

## IBM AD-AGILE USER STORY STANDARDS:
- Format: As a [role], I want [capability], so that [business benefit]
- Priority uses MoSCoW: "Must Have", "Should Have", "Could Have"
- Story points follow Fibonacci: 1, 2, 3, 5, 8, 13
- Each story belongs to an Epic (functional domain)
- Acceptance criteria must be testable and specific — reference the actual tech stack when relevant
- Stories must be independent, negotiable, valuable, estimable, small, and testable (INVEST)
- Avoid technical implementation details in the story text — focus on business value
- Acceptance criteria CAN and SHOULD reference system behaviors tied to the tech stack (e.g., specific APIs, auth flows, DB operations)

## PROJECT CONTEXT:
Name: {state["project_name"]}
Description: {state["description"]}
IBM Method: {method}
Technology Stack: {tech_summary}
Detected capabilities/services/roles: {planning_context}
Key project team: {", ".join(roles) if roles else "Project Manager, Arquitecto, Desarrollador, Analista de Negocio"}

## TAREA:
Genera 8-12 historias de usuario para este proyecto.
- Agrupa por épicas o módulos funcionales detectados en la descripción.
- Cubre autenticación/acceso solo si aplica al sistema, módulos principales, operación multi-servicio, capacidades administrativas y reportes/tableros si aplica.
- Si existen capacidades detectadas en selected_architecture.functional_modules, usa esas capacidades como guía principal de épicas.
- Si existen service_count o microservices, incluye historias para navegar, monitorear y operar cada servicio detectado desde el preview/plataforma.
- Prioriza con MoSCoW: usa "Must Have", "Should Have" o "Could Have" solo como valores de prioridad.
- Los criterios de aceptación deben estar en español, ser concretos, verificables y referir comportamientos del sistema específicos al stack tecnológico detectado.
- Varía los story points de forma realista según complejidad de implementación en el stack definido.

## CONSTRAINTS OBLIGATORIOS:
- acceptance_criteria: mínimo 3 criterios por historia. Al menos 1 debe referenciar el comportamiento específico del sistema (ej: "el endpoint POST /api/auth/login devuelve token JWT válido en <2s", "el componente muestra error si Firebase retorna código 401").
- No repetir épicas con nombres distintos para el mismo módulo funcional.
- story_points deben ser proporcionales a la complejidad real de implementación en el stack elegido, no uniformes.
- as_a: usar roles reales del sistema (administrador, usuario final, operador, auditor, etc.) — no "el usuario" genérico.
- Prohibido inventar una app de chatbot, tareas genéricas, reservas, pagos o gestión de usuarios si no está explícito en el contexto. Para Digital Workers, las historias deben hablar de trabajadores digitales, skills/tasks, validación human-in-the-loop, evidencias/documentos, reuniones, OKRs, orquestación, GRC/riesgo/cumplimiento o capacidades detectadas.

Respond with this exact JSON array:
[
  {{
    "id": "US-001",
    "epic": "<nombre de épica o módulo funcional en español>",
    "as_a": "<rol específico del sistema en español>",
    "i_want": "<capacidad concreta en español>",
    "so_that": "<beneficio de negocio concreto en español>",
    "acceptance_criteria": [
      "<criterio verificable 1 — comportamiento del sistema con referencia al stack si aplica>",
      "<criterio verificable 2>",
      "<criterio verificable 3>"
    ],
    "priority": "Must Have | Should Have | Could Have",
    "story_points": <1|2|3|5|8|13>
  }}
]
""".strip()


# ---------------------------------------------------------------------------
# Node: generate_architecture_decisions  [LLM call 3]
# ---------------------------------------------------------------------------

def generate_architecture_decisions(state: ProjectPlanState, llm_client: RemoteLLMClient) -> ProjectPlanState:
    logger.info("IBM planning node: generate_architecture_decisions")
    arch = state.get("selected_architecture") or {}
    mt = state.get("method_and_team") or {}
    prompt = _build_adr_prompt(state, arch, mt)
    raw = llm_client.generate(prompt)
    parsed = _safe_extract_json_array(raw)
    if not parsed:
        logger.warning("LLM returned unparseable response for ADRs; using fallback")
        parsed = _fallback_adrs(arch)
    return {"raw_adrs": parsed}


def _build_adr_prompt(state: ProjectPlanState, arch: dict, mt: dict) -> str:
    method = mt.get("ibm_recommended_method", "Application Development - Agile (AD-Agile)")
    tech_summary = _tech_summary_from_arch(arch, state["description"])
    planning_context = _planning_context_from_arch(arch)

    return f"""
Eres un Arquitecto de Aplicaciones de IBM Consulting documentando Architecture Decision Records (ADRs).
Tu tarea es producir ADRs para las decisiones arquitectónicas clave del proyecto.
Responde SOLO con un arreglo JSON válido. No uses markdown ni explicaciones fuera del JSON.

## IDIOMA
- Toda la salida visible debe estar en español.
- Puedes conservar nombres técnicos propios como React, FastAPI, Docker, GCP, LangGraph o ADR.
- El campo status debe usar "Accepted" o "Proposed" por contrato, pero el resto del contenido debe estar en español.

## IBM ADR FORMAT (used in IBM Method Workspace):
- Status: "Accepted" (decisions already made), "Proposed" (under review)
- Context: The problem or situation requiring a decision
- Decision: What was decided (be specific)
- Rationale: Technical and business reasoning (IBM Consulting perspective, not generic)
- Alternatives Considered: Other options that were evaluated and rejected
- Consequences: Both positive and negative consequences of this decision

## ARCHITECTURE DECISION CONTEXT:
Project: {state["project_name"]}
Description: {state["description"]}
IBM Method: {method}
Technology Stack: {tech_summary}
Detected capabilities/services/roles: {planning_context}

## TAREA:
Genera 4-6 ADRs para este proyecto.
Cubre las decisiones de mayor impacto según el stack detectado:
- Framework frontend si aplica
- Framework backend si aplica
- Estrategia de autenticación si aplica
- Selección de base de datos si aplica
- Estrategia de despliegue/nube si aplica
- Enfoque de integración IA/LLM si aplica

## CONSTRAINTS OBLIGATORIOS:
- Cada ADR DEBE referenciar la tecnología concreta elegida — nunca escribir "la tecnología seleccionada".
- Cada ADR debe conectar la decisión técnica con una capacidad real detectada, por ejemplo Digital Workers, orquestación, human-in-the-loop, documentos/evidencias, reuniones, OKRs, GRC/riesgo/cumplimiento o servicios navegables.
- alternatives_considered: mínimo 2 alternativas reales con nombre de tecnología específico en cada una.
- rationale: NUNCA escribir "es una buena opción" ni frases genéricas. Cada oración debe referenciar una característica concreta del stack o dominio descrito en el contexto.
- consequences: SIEMPRE separar con "Pro:" y "Contra:" explícitos.
- No duplicar ADRs: cada uno cubre una decisión distinta del stack.
- Prioriza las decisiones de mayor riesgo o mayor impacto arquitectónico para ESTE proyecto.

Respond with this exact JSON array:
[
  {{
    "id": "ADR-001",
    "title": "Adoptar <tecnología/patrón> para <propósito>",
    "status": "Accepted",
    "context": "<problema o decisión requerida - 2-3 oraciones en español>",
    "decision": "<decisión tomada con nombres de tecnología específicos en español>",
    "rationale": "<3-4 oraciones en español. DEBE: (1) Citar el atributo técnico principal que hace esta decisión correcta para ESTE proyecto específico (rendimiento, escalabilidad, costo, velocidad de entrega, etc.). (2) Mencionar el patrón o práctica recomendada de IBM Consulting que respalda esta elección. (3) Relacionar la decisión con una característica concreta del stack o dominio del proyecto. No escribir justificaciones genéricas — cada oración debe ser verificable y específica a ESTE engagement.>",
    "alternatives_considered": [
      "<Alternativa: [nombre específico de tecnología o patrón]. Evaluada porque [razón técnica concreta por la que fue candidata]. Descartada por: [razón técnica específica — nombrar el constraint del proyecto que la elimina, ej: 'requiere licencia Oracle incompatible con presupuesto estimado', 'latencia de cold start incompatible con SLA definido', 'curva de aprendizaje excede capacity del equipo definido'].>",
      "<Alternativa 2 — mismo formato>",
      "<Alternativa 3 — mismo formato si aplica>"
    ],
    "consequences": "Pro: <2-3 consecuencias positivas específicas y medibles para ESTE proyecto — nombrar impactos concretos en velocidad de entrega, mantenibilidad, costo operativo o experiencia de usuario>. Contra: <1-2 trade-offs reales que el equipo IBM deberá gestionar — nombrar riesgo técnico o de adopción específico con mitigación sugerida>."
  }}
]
""".strip()


# ---------------------------------------------------------------------------
# Node: compute_cost_estimate  [pure Python]
# ---------------------------------------------------------------------------

def compute_cost_estimate(state: ProjectPlanState) -> ProjectPlanState:
    logger.info("IBM planning node: compute_cost_estimate")
    mt = state.get("method_and_team") or {}
    roles = mt.get("team_roles") or []
    wbs = mt.get("wbs_phases") or []
    arch = state.get("selected_architecture") or {}

    # Project duration = sum of all phase durations (weeks), converted to months
    total_weeks = sum(p.get("duration_weeks", 0) for p in wbs) or 24
    duration_months = max(round(total_weeks / 4.333, 1), 1.0)

    # ── Labor costs ──────────────────────────────────────────────────────────
    breakdowns: list[CostRoleBreakdown] = []
    total_labor_clp = 0

    for role in roles:
        role_name = _spanish_term(role.get("role_name", "Rol"))
        seniority = role.get("seniority", "Senior")
        rate = _realistic_monthly_rate(role)
        role["monthly_rate_clp"] = rate
        dedication_weeks = int(role.get("dedication_weeks", 4))
        role_duration_months = round(dedication_weeks / 4.333, 1)
        role_total = round(rate * role_duration_months)
        total_labor_clp += role_total
        breakdowns.append(CostRoleBreakdown(
            role_name=role_name,
            seniority=seniority,
            monthly_rate_clp=rate,
            duration_months=role_duration_months,
            total_clp=role_total,
        ))

    # Setup cost (labor) = first 4 weeks across all roles
    setup_weeks = 4
    setup_cost_without = sum(
        round(_realistic_monthly_rate(r) * setup_weeks / 4.333)
        for r in roles
    )
    setup_cost_with = round(setup_cost_without * 0.45)
    savings = setup_cost_without - setup_cost_with
    savings_pct = round((savings / setup_cost_without * 100), 1) if setup_cost_without else 0.0

    # ── Cloud infrastructure costs ───────────────────────────────────────────
    cloud_provider = (arch.get("cloud") or "local").lower()
    project_profile = (arch.get("project_profile") or "standard").lower()
    has_ai = bool(arch.get("include_langgraph")) or project_profile == "ai"

    raw_services = _select_cloud_services(cloud_provider, project_profile, has_ai)
    cloud_service_models = [CloudServiceLine(**s) for s in raw_services]
    cloud_monthly = sum(s.monthly_cost_clp for s in cloud_service_models)
    cloud_setup = sum(s.setup_cost_clp for s in cloud_service_models)
    cloud_total = cloud_monthly * round(duration_months) + cloud_setup

    total_project_clp = total_labor_clp + cloud_total

    note = (
        f"Estimación basada en {len(roles)} roles IBM Consulting Chile, "
        f"duración total estimada {round(duration_months)} meses. "
        f"El costo de setup inicial (primeras 4 semanas) se reduce de "
        f"${setup_cost_without:,.0f} a ${setup_cost_with:,.0f} CLP ({savings_pct}% de ahorro) "
        f"al utilizar la plataforma generadora de arquitecturas IBM. "
    )
    if cloud_provider != "local" and cloud_service_models:
        note += (
            f"Infraestructura cloud ({cloud_provider.upper()}): "
            f"${cloud_monthly:,.0f} CLP/mes + ${cloud_setup:,.0f} CLP de setup inicial "
            f"= ${cloud_total:,.0f} CLP total en {round(duration_months)} meses."
        )

    plan_state_update: dict = {}
    plan_state_update["method_and_team"] = {
        **(mt),
        "_cost_estimate": CostEstimate(
            currency="CLP",
            project_duration_months=round(duration_months),
            roles_breakdown=breakdowns,
            total_project_cost_clp=total_project_clp,
            setup_cost_without_solution_clp=setup_cost_without,
            setup_cost_with_solution_clp=setup_cost_with,
            estimated_savings_clp=savings,
            savings_percentage=savings_pct,
            methodology_note=note,
            cloud_provider=cloud_provider,
            cloud_services=cloud_service_models,
            cloud_monthly_cost_clp=cloud_monthly,
            cloud_total_cost_clp=cloud_total,
            cloud_setup_cost_clp=cloud_setup,
        ),
    }
    return plan_state_update


# ---------------------------------------------------------------------------
# Node: assemble_plan  [pure Python]
# ---------------------------------------------------------------------------

def assemble_plan(state: ProjectPlanState) -> ProjectPlanState:
    logger.info("IBM planning node: assemble_plan")
    mt = state.get("method_and_team") or {}
    cost_estimate: CostEstimate = mt.pop("_cost_estimate", None) or CostEstimate()

    team_roles = [_parse_ibm_role(r) for r in (mt.get("team_roles") or [])]
    wbs_phases = [_parse_wbs_phase(p) for p in (mt.get("wbs_phases") or [])]
    user_stories = [_parse_user_story(s, i) for i, s in enumerate(state.get("raw_user_stories") or [])]
    adrs = [_parse_adr(a, i) for i, a in enumerate(state.get("raw_adrs") or [])]

    plan = IBMProjectPlan(
        ibm_recommended_method=str(mt.get("ibm_recommended_method", "Application Development - Agile (AD-Agile)")),
        ibm_method_rationale=_spanish_term(mt.get("ibm_method_rationale", "")),
        service_line=_spanish_term(mt.get("service_line", "Hybrid Cloud & Data")),
        project_overview=_spanish_term(mt.get("project_overview", state["description"][:180])),
        adoption_journey=str(mt.get("adoption_journey", "Delivery")),
        tailoring_notes=_spanish_term(mt.get("tailoring_notes", "")),
        team_roles=team_roles,
        user_stories=user_stories,
        wbs_phases=wbs_phases,
        architecture_decisions=adrs,
        cost_estimate=cost_estimate,
        project_risks=[_spanish_term(r) for r in (mt.get("project_risks") or [])],
        ibm_assets_recommended=[_spanish_term(a) for a in (mt.get("ibm_assets_recommended") or [])],
    )
    return {"plan": plan}


# ---------------------------------------------------------------------------
# Parsers – tolerant converters from raw LLM dicts to Pydantic models
# ---------------------------------------------------------------------------

def _parse_ibm_role(raw: Any) -> IBMRole:
    if not isinstance(raw, dict):
        return IBMRole()
    return IBMRole(
        role_name=_spanish_term(raw.get("role_name", "")),
        ibm_method_workspace_role=str(raw.get("ibm_method_workspace_role", "")),
        seniority=_coerce_seniority(raw.get("seniority")),
        phase=_spanish_term(raw.get("phase", "All")),
        dedication_weeks=_coerce_int(raw.get("dedication_weeks"), 4, 1, 52),
        monthly_rate_clp=_realistic_monthly_rate(raw),
        justification=str(raw.get("justification", "")),
    )


def _parse_wbs_phase(raw: Any) -> WBSPhase:
    if not isinstance(raw, dict):
        return WBSPhase()
    tasks = []
    for t in _as_list(raw.get("tasks")):
        if isinstance(t, dict):
            tasks.append(WBSTask(
                task=_spanish_term(t.get("task", "")),
                responsible_role=_spanish_term(t.get("responsible_role", "")),
                effort_days=max(0.5, float(t.get("effort_days", 1.0))),
            ))
    return WBSPhase(
        phase_name=_spanish_term(raw.get("phase_name", "")),
        ibm_method_phase=_spanish_term(raw.get("ibm_method_phase", "")),
        duration_weeks=_coerce_int(raw.get("duration_weeks"), 2, 1),
        objectives=[_spanish_term(item) for item in _as_str_list(raw.get("objectives"))],
        tasks=tasks,
        deliverables=[_spanish_term(item) for item in _as_str_list(raw.get("deliverables"))],
    )


def _parse_user_story(raw: Any, index: int) -> UserStory:
    if not isinstance(raw, dict):
        return UserStory(id=f"US-{index + 1:03d}")
    return UserStory(
        id=str(raw.get("id", f"US-{index + 1:03d}")),
        epic=_spanish_term(raw.get("epic", "")),
        as_a=_spanish_term(raw.get("as_a", "")),
        i_want=_spanish_term(raw.get("i_want", "")),
        so_that=_spanish_term(raw.get("so_that", "")),
        acceptance_criteria=[_spanish_term(item) for item in _as_str_list(raw.get("acceptance_criteria"))],
        priority=_coerce_priority(raw.get("priority")),
        story_points=_coerce_story_points(raw.get("story_points")),
    )


def _parse_adr(raw: Any, index: int) -> ADR:
    if not isinstance(raw, dict):
        return ADR(id=f"ADR-{index + 1:03d}")
    return ADR(
        id=str(raw.get("id", f"ADR-{index + 1:03d}")),
        title=_spanish_term(raw.get("title", "")),
        status=str(raw.get("status", "Accepted")),
        context=_spanish_term(raw.get("context", "")),
        decision=_spanish_term(raw.get("decision", "")),
        rationale=_spanish_term(raw.get("rationale", "")),
        alternatives_considered=[_spanish_term(item) for item in _as_str_list(raw.get("alternatives_considered"))],
        consequences=_spanish_term(raw.get("consequences", "")),
    )


# ---------------------------------------------------------------------------
# Fallbacks (used when LLM fails or returns bad JSON)
# ---------------------------------------------------------------------------

def _fallback_method_and_team(state: ProjectPlanState) -> dict:
    desc = state["description"].lower()
    if any(k in desc for k in ["ia", "ai", "agente", "llm", "langgraph", "chatbot", "watson"]):
        method = "AI Integration"
        service_line = "Hybrid Cloud & Data"
        phases = [
            {"phase_name": "AI Strategy", "ibm_method_phase": "AI Strategy", "duration_weeks": 3,
             "objectives": ["Definir casos de uso IA", "Seleccionar modelos LLM"],
             "tasks": [{"task": "Taller de casos de uso IA", "responsible_role": "Business Analyst", "effort_days": 3},
                       {"task": "Evaluación de modelos LLM", "responsible_role": "Automation Architect", "effort_days": 5}],
             "deliverables": ["AI Use Cases List", "LLM Selection Report"]},
            {"phase_name": "AI Build", "ibm_method_phase": "AI Build", "duration_weeks": 10,
             "objectives": ["Implementar agentes IA", "Integrar con plataforma"],
             "tasks": [{"task": "Desarrollo de grafo LangGraph", "responsible_role": "Application Developer", "effort_days": 20},
                       {"task": "Integración API LLM", "responsible_role": "Automation Architect", "effort_days": 10}],
             "deliverables": ["AI Agent v1", "Integration Tests"]},
        ]
        roles = [
            {"role_name": "Project Manager", "ibm_method_workspace_role": "Client Project Manager",
             "seniority": "Senior", "phase": "All", "dedication_weeks": 24, "monthly_rate_clp": 7_000_000,
             "justification": "Gestión del engagement y coordinación con el cliente."},
            {"role_name": "AI Architect", "ibm_method_workspace_role": "Automation Architect",
             "seniority": "Senior", "phase": "All", "dedication_weeks": 20, "monthly_rate_clp": 7_500_000,
             "justification": "Diseño de la arquitectura de agentes IA y flujos LangGraph."},
            {"role_name": "Developer", "ibm_method_workspace_role": "Application Developer",
             "seniority": "Senior", "phase": "AI Build", "dedication_weeks": 16, "monthly_rate_clp": 5_000_000,
             "justification": "Implementación de features y integración frontend/backend."},
        ]
    else:
        method = "Application Development - Agile (AD-Agile)"
        service_line = "Application Operations, Hybrid Cloud & Data"
        phases = [
            {"phase_name": "Iteration 0", "ibm_method_phase": "Iteration 0", "duration_weeks": 3,
             "objectives": ["Setup del proyecto", "Definición de arquitectura"],
             "tasks": [{"task": "Definición de arquitectura base", "responsible_role": "Architect", "effort_days": 5},
                       {"task": "Configuración del entorno de desarrollo", "responsible_role": "DevOps Lead", "effort_days": 3}],
             "deliverables": ["Architecture Overview", "Development Environment"]},
            {"phase_name": "Iterations", "ibm_method_phase": "Iterations 1-n", "duration_weeks": 16,
             "objectives": ["Desarrollo de features por sprint", "Entrega incremental"],
             "tasks": [{"task": "Sprint planning y desarrollo", "responsible_role": "Developer", "effort_days": 60},
                       {"task": "QA y testing continuo", "responsible_role": "QA Engineer", "effort_days": 20}],
             "deliverables": ["Working Software", "Sprint Reviews", "Test Reports"]},
            {"phase_name": "Close", "ibm_method_phase": "Close", "duration_weeks": 2,
             "objectives": ["Entrega final", "Documentación"],
             "tasks": [{"task": "Go-live y soporte", "responsible_role": "Project Manager", "effort_days": 5}],
             "deliverables": ["Deployed Application", "User Documentation"]},
        ]
        roles = [
            {"role_name": "Project Manager", "ibm_method_workspace_role": "Client Project Manager",
             "seniority": "Senior", "phase": "All", "dedication_weeks": 21, "monthly_rate_clp": 7_000_000,
             "justification": "Gestión del engagement, control de scope y stakeholders."},
            {"role_name": "Solution Architect", "ibm_method_workspace_role": "Application Architect: Hybrid Cloud",
             "seniority": "Senior", "phase": "All", "dedication_weeks": 18, "monthly_rate_clp": 8_500_000,
             "justification": "Diseño de la arquitectura de la solución y decisiones técnicas."},
            {"role_name": "Business Analyst", "ibm_method_workspace_role": "Business Analyst",
             "seniority": "Senior", "phase": "Iteration 0 + Iterations", "dedication_weeks": 15, "monthly_rate_clp": 5_000_000,
             "justification": "Levantamiento de requerimientos y definición de user stories."},
            {"role_name": "Developer", "ibm_method_workspace_role": "Application Developer",
             "seniority": "Senior", "phase": "Iterations", "dedication_weeks": 16, "monthly_rate_clp": 5_000_000,
             "justification": "Desarrollo fullstack de las funcionalidades del producto."},
            {"role_name": "DevOps Lead", "ibm_method_workspace_role": "Application Developer: DevOps",
             "seniority": "Senior", "phase": "Iteration 0 + Iterations", "dedication_weeks": 12, "monthly_rate_clp": 6_000_000,
             "justification": "Configuración del pipeline CI/CD, Docker, y entorno de despliegue."},
        ]

    return {
        "ibm_recommended_method": method,
        "ibm_method_rationale": f"El método {method} es el más adecuado para este proyecto según las características descritas.",
        "service_line": service_line,
        "project_overview": f"Proyecto {state['project_name']}: {state['description'][:200]}",
        "adoption_journey": "Delivery",
        "tailoring_notes": "El método fue aplicado sin modificaciones mayores dado el alcance estándar del engagement.",
        "team_roles": roles,
        "wbs_phases": phases,
        "project_risks": [
            "Cambios en requerimientos durante el desarrollo que impacten el scope acordado.",
            "Disponibilidad de stakeholders del cliente para validaciones y sign-offs.",
            "Integración con sistemas externos del cliente con documentación insuficiente.",
            "Curva de aprendizaje del equipo con herramientas y patrones IBM seleccionados.",
        ],
        "ibm_assets_recommended": [
            "Architecture Overview Document",
            "Implementation Project Plan",
            "Acceptance Test Plan",
            "Change Management (Agile and Traditional)",
            "Configuration Management",
        ],
    }


def _fallback_user_stories(state: ProjectPlanState) -> list[dict]:
    arch = state.get("selected_architecture") or {}
    modules = _as_str_list(arch.get("functional_modules") or arch.get("modules"))
    service_count = _coerce_int(arch.get("service_count"), 0, 0, 12)

    if modules:
        stories = [
            {
                "id": "US-001", "epic": "Acceso y Seguridad",
                "as_a": "operador autorizado", "i_want": "iniciar sesión con permisos asociados a mi rol",
                "so_that": "pueda operar las capacidades de la plataforma sin exponer información sensible",
                "acceptance_criteria": [
                    "Firebase valida credenciales y retorna una sesión activa antes de mostrar el workspace",
                    "El frontend oculta capacidades no autorizadas según el rol recibido desde la API",
                    "Los intentos fallidos muestran un mensaje claro sin revelar detalles internos del sistema",
                ],
                "priority": "Must Have", "story_points": 5,
            }
        ]
        for idx, module in enumerate(modules[:8], start=2):
            label = module.replace("-", " ")
            stories.append({
                "id": f"US-{idx:03d}", "epic": label.title(),
                "as_a": "operador de la plataforma",
                "i_want": f"gestionar la capacidad {label}",
                "so_that": "pueda ejecutar el servicio comprometido con trazabilidad y control operacional",
                "acceptance_criteria": [
                    f"El frontend React muestra una vista navegable para {label} con estado de carga, vacío y error",
                    f"FastAPI expone endpoints versionados para consultar y actualizar información de {label}",
                    "Cada acción relevante queda registrada con usuario, fecha, resultado y evidencia asociada",
                ],
                "priority": "Must Have" if idx <= 4 else "Should Have",
                "story_points": 5 if idx <= 4 else 3,
            })
        if service_count > 1:
            stories.append({
                "id": f"US-{len(stories) + 1:03d}", "epic": "Servicios Navegables",
                "as_a": "administrador operativo",
                "i_want": "navegar entre los servicios detectados desde una consola central",
                "so_that": "pueda visualizar estado, responsables y evidencia de cada servicio sin cambiar de herramienta",
                "acceptance_criteria": [
                    f"El preview muestra {service_count} servicios accesibles desde la navegación principal",
                    "Cada servicio conserva su propio estado, métricas y últimos eventos operativos",
                    "La API retorna errores por servicio sin bloquear la navegación del resto de la plataforma",
                ],
                "priority": "Should Have", "story_points": 5,
            })
        return stories[:12]

    return [
        {
            "id": "US-001", "epic": "Acceso y Seguridad",
            "as_a": "usuario registrado", "i_want": "iniciar sesión de forma segura",
            "so_that": "pueda acceder a las funcionalidades del sistema",
            "acceptance_criteria": [
                "El sistema autentica al usuario con credenciales válidas en menos de 2 segundos",
                "Los intentos fallidos de login bloquean la cuenta tras 5 intentos",
                "La sesión expira automáticamente tras 30 minutos de inactividad",
            ],
            "priority": "Must Have", "story_points": 5,
        },
        {
            "id": "US-002", "epic": "Dashboard",
            "as_a": "administrador", "i_want": "visualizar un dashboard con métricas clave",
            "so_that": "pueda monitorear el estado del sistema en tiempo real",
            "acceptance_criteria": [
                "El dashboard carga en menos de 3 segundos",
                "Las métricas se actualizan automáticamente cada 5 minutos",
                "El administrador puede exportar los datos en formato CSV",
            ],
            "priority": "Must Have", "story_points": 8,
        },
        {
            "id": "US-003", "epic": "Gestión de Usuarios",
            "as_a": "administrador", "i_want": "crear, editar y desactivar cuentas de usuario",
            "so_that": "pueda gestionar el acceso al sistema de forma centralizada",
            "acceptance_criteria": [
                "El administrador puede crear un usuario con nombre, email y rol",
                "El sistema envía un email de bienvenida al usuario creado",
                "Un usuario desactivado no puede iniciar sesión",
            ],
            "priority": "Must Have", "story_points": 5,
        },
    ]


def _fallback_adrs(arch: dict) -> list[dict]:
    adrs = []
    if arch.get("frontend") in ("react", "none") or True:
        adrs.append({
            "id": "ADR-001", "title": "Adoptar React + Vite para el frontend",
            "status": "Accepted",
            "context": "El proyecto requiere una experiencia frontend moderna, performante y alineada con estándares de entrega IBM Consulting.",
            "decision": "Usar React 18 con Vite como herramienta de build y React Router para navegación SPA.",
            "rationale": "React entrega un ecosistema maduro para productos digitales y Vite acelera el ciclo de desarrollo con hot reload y builds optimizados.",
            "alternatives_considered": ["Angular: descartado por mayor curva de aprendizaje para este alcance", "Vue.js: descartado por menor alineación con los activos internos disponibles"],
            "consequences": "El equipo gana velocidad y reutilización de componentes, pero debe mantener una arquitectura disciplinada para evitar acoplamiento excesivo.",
        })
    if arch.get("backend") in ("fastapi", "none") or True:
        adrs.append({
            "id": "ADR-002", "title": "Adoptar FastAPI para la API backend",
            "status": "Accepted",
            "context": "El proyecto requiere un backend Python de alto rendimiento con documentación automática de API.",
            "decision": "Usar FastAPI con servidor ASGI Uvicorn y Pydantic para validación de contratos de datos.",
            "rationale": "La documentación OpenAPI/Swagger automática de FastAPI se alinea con una entrega API-first y reduce fricción entre frontend, backend y QA.",
            "alternatives_considered": ["Django REST Framework: descartado por ser más pesado para una API modular", "Flask: descartado por requerir más configuración manual para contratos y OpenAPI"],
            "consequences": "Se acelera el desarrollo de endpoints y documentación, pero el equipo debe cuidar dependencias async y configuración de despliegue.",
        })
    return adrs


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _safe_extract_json(raw: str) -> Optional[dict]:
    try:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        text = fenced.group(1) if fenced else raw
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None
        return json.loads(text[start:end + 1])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None


def _safe_extract_json_array(raw: str) -> Optional[list]:
    try:
        fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if fenced:
            return json.loads(fenced.group(1))
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            return None
        return json.loads(raw[start:end + 1])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None


def _mentions_unrequested_chatbot(value: Any, description: str) -> bool:
    desc = description.lower()
    if any(term in desc for term in ("chatbot", "chat bot", "asistente conversacional", "bot conversacional")):
        return False
    try:
        serialized = json.dumps(value, ensure_ascii=False).lower()
    except TypeError:
        serialized = str(value).lower()
    return any(term in serialized for term in ("chatbot", "chat bot", "asistente conversacional", "bot conversacional"))


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------

def _coerce_int(value: Any, default: int, minimum: int = 0, maximum: int = 10_000_000_000) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _realistic_monthly_rate(role: dict[str, Any]) -> int:
    raw_rate = _coerce_int(role.get("monthly_rate_clp"), DEFAULT_MONTHLY_RATE_CLP, 0)
    inferred_rate = _infer_monthly_rate(role)
    if raw_rate < MIN_REALISTIC_MONTHLY_RATE_CLP:
        return inferred_rate
    return max(raw_rate, MIN_REALISTIC_MONTHLY_RATE_CLP)


def _infer_monthly_rate(role: dict[str, Any]) -> int:
    role_text = " ".join(
        str(role.get(key, ""))
        for key in ("ibm_method_workspace_role", "role_name")
    ).strip().lower()
    seniority = _coerce_seniority(role.get("seniority")).lower()

    for label, rate in ROLE_RATE_TABLE_CLP.items():
        if label in role_text:
            if seniority == "mid" and rate == 5_000_000:
                return 3_500_000
            if seniority == "junior" and "developer" in role_text:
                return 2_500_000
            return rate

    return DEFAULT_MONTHLY_RATE_CLP


def _spanish_term(value: Any) -> str:
    text = str(value or "")
    if not text:
        return text
    for source, target in sorted(SPANISH_TERM_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(rf"\b{re.escape(source)}\b", target, text, flags=re.IGNORECASE)
    return text


def _coerce_seniority(value: Any) -> str:
    v = str(value or "").strip().title()
    return v if v in ("Senior", "Mid", "Junior") else "Senior"


def _coerce_priority(value: Any) -> str:
    v = str(value or "").strip()
    return v if v in ("Must Have", "Should Have", "Could Have") else "Should Have"


def _coerce_story_points(value: Any) -> int:
    valid = {1, 2, 3, 5, 8, 13}
    try:
        v = int(value)
        return v if v in valid else min(valid, key=lambda x: abs(x - v))
    except (TypeError, ValueError):
        return 3


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    return []


def _as_str_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if item]


def _tech_summary_from_arch(arch: dict, description: str) -> str:
    if arch:
        parts = []
        if arch.get("frontend") and arch["frontend"] != "none":
            parts.append(f"Frontend: React + Vite")
        if arch.get("backend") and arch["backend"] != "none":
            parts.append(f"Backend: FastAPI (Python)")
        if arch.get("database") and arch["database"] != "none":
            parts.append(f"Database: {arch['database']}")
        if arch.get("auth") and arch["auth"] != "none":
            parts.append(f"Auth: {arch['auth']}")
        if arch.get("cloud") and arch["cloud"] != "local":
            parts.append(f"Cloud: {arch['cloud'].upper()}")
        if arch.get("include_langgraph"):
            parts.append("AI: LangGraph + LLM agents")
        if arch.get("include_services") and arch.get("service_count"):
            parts.append(f"Servicios navegables: {arch.get('service_count')}")
        return ", ".join(parts) if parts else description[:200]
    return description[:200]


def _planning_context_from_arch(arch: dict) -> str:
    if not arch:
        return "No hay arquitectura detectada; usar solo la descripcion."

    parts = []
    modules = _as_str_list(arch.get("functional_modules") or arch.get("modules"))
    navigation = _as_str_list(arch.get("navigation_sections"))
    roles = _as_str_list(arch.get("roles"))
    services = _as_str_list(arch.get("microservices") or arch.get("services"))
    integrations = _as_str_list(arch.get("integrations"))

    if modules:
        parts.append(f"capacidades={', '.join(modules[:12])}")
    if navigation:
        parts.append(f"navegacion={', '.join(navigation[:12])}")
    if roles:
        parts.append(f"roles_operativos={', '.join(roles[:10])}")
    if arch.get("include_services") or arch.get("service_count"):
        count = arch.get("service_count") or len(services) or "varios"
        service_label = f"servicios_navegables={count}"
        if services:
            service_label += f" ({', '.join(services[:8])})"
        parts.append(service_label)
    if integrations:
        parts.append(f"integraciones={', '.join(integrations[:8])}")
    if arch.get("project_profile"):
        parts.append(f"perfil={arch.get('project_profile')}")

    return "; ".join(parts) if parts else "Arquitectura base sin capacidades explicitas."
