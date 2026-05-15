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
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.models import (
    ADR,
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
    graph.add_node("generate_user_stories", lambda s: generate_user_stories(s, client))
    graph.add_node("generate_architecture_decisions", lambda s: generate_architecture_decisions(s, client))
    graph.add_node("compute_cost_estimate", compute_cost_estimate)
    graph.add_node("assemble_plan", assemble_plan)

    graph.set_entry_point("receive_plan_request")
    graph.add_edge("receive_plan_request", "generate_method_and_team")
    graph.add_edge("generate_method_and_team", "generate_user_stories")
    graph.add_edge("generate_user_stories", "generate_architecture_decisions")
    graph.add_edge("generate_architecture_decisions", "compute_cost_estimate")
    graph.add_edge("compute_cost_estimate", "assemble_plan")
    graph.add_edge("assemble_plan", END)
    return graph.compile()


def plan_project_with_ai(
    description: str,
    project_name: str,
    selected_architecture: Optional[dict] = None,
    llm_client: Optional[RemoteLLMClient] = None,
) -> IBMProjectPlan:
    logger.info("Starting IBM project planning graph for: %s", project_name)
    app = build_project_planning_graph(llm_client)
    final_state = app.invoke({
        "description": description.strip(),
        "project_name": project_name.strip().lower().replace(" ", "-"),
        "selected_architecture": selected_architecture or {},
    })
    plan = final_state.get("plan")
    if not isinstance(plan, IBMProjectPlan):
        raise RuntimeError("El grafo de planificación IBM no produjo un plan válido.")
    return plan


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
    return {"method_and_team": parsed}


def _build_method_and_team_prompt(state: ProjectPlanState) -> str:
    arch = state.get("selected_architecture") or {}
    arch_summary = json.dumps({k: v for k, v in arch.items() if k in (
        "project_type", "frontend", "backend", "database", "auth",
        "cloud", "project_profile", "include_langgraph",
    )}, ensure_ascii=False) if arch else "{}"

    return f"""
You are a Senior IBM Consulting Solution Architect with full access to the IBM Method Workspace catalogue.
Your task is to produce a complete IBM delivery plan for a new project engagement.
Respond ONLY with valid JSON. No markdown, no explanation outside the JSON.

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

## PROJECT TO PLAN:
Name: {state["project_name"]}
Description: {state["description"]}
Technical architecture selected: {arch_summary}

## TASK:
Using the complete IBM Method Workspace knowledge above, select the single best-fit method
and produce the full delivery plan. The method MUST be justified by domain and nature —
do not default to AD-Agile unless it genuinely fits a custom app dev engagement.

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
  "ibm_method_rationale": "<2-3 sentences explaining why this method fits this specific project>",
  "service_line": "<primary service line abbreviation and name>",
  "project_overview": "<2-3 sentences describing the project from IBM Consulting perspective>",
  "adoption_journey": "Delivery | Solutioning",
  "tailoring_notes": "<1-2 sentences on how this standard method was adapted for this specific engagement>",
  "team_roles": [
    {{
      "role_name": "<SHORT functional name — e.g. 'Project Manager', 'Solution Architect', 'Developer'>",
      "ibm_method_workspace_role": "<exact IBM MW role name from the list above>",
      "seniority": "Senior | Mid | Junior",
      "phase": "<All | specific phase name from the selected method>",
      "dedication_weeks": <integer 1-52>,
      "monthly_rate_clp": <integer from the rate table above>,
      "justification": "<1-2 sentences specific to THIS project>"
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
    "<risk specific to this project type and stack — not generic>",
    "<risk 2>",
    "<risk 3>",
    "<risk 4>"
  ],
  "ibm_assets_recommended": [
    "<IBM Method Workspace work product or asset name>",
    "<asset 2>",
    "<asset 3>",
    "<asset 4>"
  ]
}}

CONSTRAINTS:
- team_roles: 5-7 roles minimum. Every project needs PM + Architect + Developer.
  AI projects require Automation Architect. Data projects require Data Architect.
  QE-focused projects require Application Architect: Quality Engineering.
  role_name MUST be a short label (2-4 words) used as the display name in the plan.
- wbs_phases: 3-5 phases using the EXACT phase names from the selected method as listed above.
  Each phase: 3-5 tasks, 2-3 deliverables.
  tasks[].responsible_role MUST exactly match one of the role_name values from team_roles.
- project_risks: 4-5 risks, each actionable and specific to the project stack/domain.
- ibm_assets_recommended: 4-6 IBM MW work products relevant to this exact engagement.
""".strip()


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
    return {"raw_user_stories": parsed}


def _build_user_stories_prompt(state: ProjectPlanState, mt: dict) -> str:
    roles = [r.get("role_name", "") for r in mt.get("team_roles", [])]
    method = mt.get("ibm_recommended_method", "Application Development - Agile (AD-Agile)")

    return f"""
You are an IBM Consulting Business Analyst applying the AD-Agile method.
Your task is to generate User Stories for an IBM project engagement.
Respond ONLY with a valid JSON array. No markdown, no explanation outside the JSON.

## IBM AD-AGILE USER STORY STANDARDS:
- Format: As a [role], I want [capability], so that [business benefit]
- Priority uses MoSCoW: "Must Have", "Should Have", "Could Have"
- Story points follow Fibonacci: 1, 2, 3, 5, 8, 13
- Each story belongs to an Epic (functional domain)
- Acceptance criteria must be testable and specific
- Stories must be independent, negotiable, valuable, estimable, small, and testable (INVEST)
- Avoid technical implementation details in the story text — focus on business value

## PROJECT CONTEXT:
Name: {state["project_name"]}
Description: {state["description"]}
IBM Method: {method}
Key project team: {", ".join(roles) if roles else "Project Manager, Architect, Developer, Business Analyst"}

## TASK:
Generate 8-12 User Stories for this project.
- Group stories by Epics (functional domains detected from the description)
- Cover: authentication/access, main functional modules, admin capabilities, reporting/dashboard if relevant
- Prioritize by MoSCoW: most critical features are "Must Have", enhancements are "Should Have"
- Make acceptance criteria concrete (3-4 per story)
- Vary story point estimates realistically (not everything is 5 points)

Respond with this exact JSON array:
[
  {{
    "id": "US-001",
    "epic": "<epic name matching a functional module>",
    "as_a": "<user role in the system>",
    "i_want": "<concrete capability>",
    "so_that": "<business benefit>",
    "acceptance_criteria": [
      "<testable criterion 1>",
      "<testable criterion 2>",
      "<testable criterion 3>"
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

    return f"""
You are an IBM Consulting Application Architect documenting Architecture Decision Records (ADRs).
Your task is to produce ADRs for the key architectural decisions in an IBM project.
Respond ONLY with a valid JSON array. No markdown, no explanation outside the JSON.

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

## TASK:
Generate 4-6 Architecture Decision Records for this project.
Cover the most impactful decisions based on the technology stack detected:
- Frontend framework decision (if applicable)
- Backend framework decision (if applicable)
- Authentication strategy decision (if applicable)
- Database selection decision (if applicable)
- Deployment/cloud strategy decision (if applicable)
- AI/LLM integration approach (if AI is in scope)

Make the ADRs specific to THIS project, not generic. Reference the IBM Method Workspace
and IBM's recommended patterns where relevant.

Respond with this exact JSON array:
[
  {{
    "id": "ADR-001",
    "title": "Adopt <technology/pattern> for <purpose>",
    "status": "Accepted",
    "context": "<what problem or decision was required - 2-3 sentences>",
    "decision": "<what was decided - be specific with technology names>",
    "rationale": "<why this decision was made from IBM Consulting perspective - 2-3 sentences>",
    "alternatives_considered": [
      "<alternative 1 and why rejected>",
      "<alternative 2 and why rejected>"
    ],
    "consequences": "<positive and negative consequences - 2-3 sentences>"
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

    # Project duration = max of all phase durations (weeks), converted to months
    total_weeks = sum(p.get("duration_weeks", 0) for p in wbs) or 24
    duration_months = max(round(total_weeks / 4.333, 1), 1.0)

    breakdowns: list[CostRoleBreakdown] = []
    total_clp = 0

    for role in roles:
        role_name = role.get("role_name", "Role")
        seniority = role.get("seniority", "Senior")
        rate = int(role.get("monthly_rate_clp", 5_000_000))
        dedication_weeks = int(role.get("dedication_weeks", 4))
        role_duration_months = round(dedication_weeks / 4.333, 1)
        role_total = round(rate * role_duration_months)
        total_clp += role_total
        breakdowns.append(CostRoleBreakdown(
            role_name=role_name,
            seniority=seniority,
            monthly_rate_clp=rate,
            duration_months=role_duration_months,
            total_clp=role_total,
        ))

    # Setup cost = cost of first 4 weeks across all roles
    setup_weeks = 4
    setup_cost_without = sum(
        round(int(r.get("monthly_rate_clp", 5_000_000)) * setup_weeks / 4.333)
        for r in roles
    )
    # With the platform solution, setup is reduced by ~55% (from 4 weeks to ~1.8 weeks)
    setup_cost_with = round(setup_cost_without * 0.45)
    savings = setup_cost_without - setup_cost_with
    savings_pct = round((savings / setup_cost_without * 100), 1) if setup_cost_without else 0.0

    note = (
        f"Estimación basada en {len(roles)} roles IBM Consulting Chile, "
        f"duración total estimada {duration_months} meses. "
        f"El costo de setup inicial (primeras 4 semanas) se reduce de "
        f"${setup_cost_without:,.0f} a ${setup_cost_with:,.0f} CLP ({savings_pct}% de ahorro) "
        f"al utilizar la plataforma generadora de arquitecturas IBM."
    )

    plan_state_update: dict = {}
    plan_state_update["method_and_team"] = {
        **(mt),
        "_cost_estimate": CostEstimate(
            currency="CLP",
            project_duration_months=round(duration_months),
            roles_breakdown=breakdowns,
            total_project_cost_clp=total_clp,
            setup_cost_without_solution_clp=setup_cost_without,
            setup_cost_with_solution_clp=setup_cost_with,
            estimated_savings_clp=savings,
            savings_percentage=savings_pct,
            methodology_note=note,
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
        ibm_method_rationale=str(mt.get("ibm_method_rationale", "")),
        service_line=str(mt.get("service_line", "Hybrid Cloud & Data")),
        project_overview=str(mt.get("project_overview", state["description"][:180])),
        adoption_journey=str(mt.get("adoption_journey", "Delivery")),
        tailoring_notes=str(mt.get("tailoring_notes", "")),
        team_roles=team_roles,
        user_stories=user_stories,
        wbs_phases=wbs_phases,
        architecture_decisions=adrs,
        cost_estimate=cost_estimate,
        project_risks=[str(r) for r in (mt.get("project_risks") or [])],
        ibm_assets_recommended=[str(a) for a in (mt.get("ibm_assets_recommended") or [])],
    )
    return {"plan": plan}


# ---------------------------------------------------------------------------
# Parsers – tolerant converters from raw LLM dicts to Pydantic models
# ---------------------------------------------------------------------------

def _parse_ibm_role(raw: Any) -> IBMRole:
    if not isinstance(raw, dict):
        return IBMRole()
    return IBMRole(
        role_name=str(raw.get("role_name", "")),
        ibm_method_workspace_role=str(raw.get("ibm_method_workspace_role", "")),
        seniority=_coerce_seniority(raw.get("seniority")),
        phase=str(raw.get("phase", "All")),
        dedication_weeks=_coerce_int(raw.get("dedication_weeks"), 4, 1, 52),
        monthly_rate_clp=_coerce_int(raw.get("monthly_rate_clp"), 5_000_000, 0),
        justification=str(raw.get("justification", "")),
    )


def _parse_wbs_phase(raw: Any) -> WBSPhase:
    if not isinstance(raw, dict):
        return WBSPhase()
    tasks = []
    for t in _as_list(raw.get("tasks")):
        if isinstance(t, dict):
            tasks.append(WBSTask(
                task=str(t.get("task", "")),
                responsible_role=str(t.get("responsible_role", "")),
                effort_days=max(0.5, float(t.get("effort_days", 1.0))),
            ))
    return WBSPhase(
        phase_name=str(raw.get("phase_name", "")),
        ibm_method_phase=str(raw.get("ibm_method_phase", "")),
        duration_weeks=_coerce_int(raw.get("duration_weeks"), 2, 1),
        objectives=_as_str_list(raw.get("objectives")),
        tasks=tasks,
        deliverables=_as_str_list(raw.get("deliverables")),
    )


def _parse_user_story(raw: Any, index: int) -> UserStory:
    if not isinstance(raw, dict):
        return UserStory(id=f"US-{index + 1:03d}")
    return UserStory(
        id=str(raw.get("id", f"US-{index + 1:03d}")),
        epic=str(raw.get("epic", "")),
        as_a=str(raw.get("as_a", "")),
        i_want=str(raw.get("i_want", "")),
        so_that=str(raw.get("so_that", "")),
        acceptance_criteria=_as_str_list(raw.get("acceptance_criteria")),
        priority=_coerce_priority(raw.get("priority")),
        story_points=_coerce_story_points(raw.get("story_points")),
    )


def _parse_adr(raw: Any, index: int) -> ADR:
    if not isinstance(raw, dict):
        return ADR(id=f"ADR-{index + 1:03d}")
    return ADR(
        id=str(raw.get("id", f"ADR-{index + 1:03d}")),
        title=str(raw.get("title", "")),
        status=str(raw.get("status", "Accepted")),
        context=str(raw.get("context", "")),
        decision=str(raw.get("decision", "")),
        rationale=str(raw.get("rationale", "")),
        alternatives_considered=_as_str_list(raw.get("alternatives_considered")),
        consequences=str(raw.get("consequences", "")),
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
            "id": "ADR-001", "title": "Adopt React + Vite for Frontend",
            "status": "Accepted",
            "context": "The project requires a modern, performant frontend framework aligned with IBM Consulting delivery standards.",
            "decision": "Use React 18 with Vite as the build tool and React Router for SPA navigation.",
            "rationale": "React is IBM's preferred frontend framework for digital products. Vite provides fast hot-reload and optimized builds, aligned with IBM DevSecOps CI/CD standards.",
            "alternatives_considered": ["Angular — rejected due to higher learning curve and slower iteration", "Vue.js — rejected as IBM Consulting has less internal expertise"],
            "consequences": "Team benefits from large ecosystem and IBM internal assets. Requires disciplined component architecture to avoid prop-drilling.",
        })
    if arch.get("backend") in ("fastapi", "none") or True:
        adrs.append({
            "id": "ADR-002", "title": "Adopt FastAPI for Backend API",
            "status": "Accepted",
            "context": "The project requires a high-performance Python backend with automatic API documentation.",
            "decision": "Use FastAPI with Uvicorn ASGI server and Pydantic for data validation.",
            "rationale": "FastAPI's automatic OpenAPI/Swagger documentation aligns with IBM's API-first delivery standard. Pydantic enforces data contracts consistently.",
            "alternatives_considered": ["Django REST Framework — rejected as heavier for microservices-style API", "Flask — rejected as lacks automatic data validation and OpenAPI generation"],
            "consequences": "Faster API development with built-in docs. Requires Python 3.9+ and async-aware database drivers.",
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


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------

def _coerce_int(value: Any, default: int, minimum: int = 0, maximum: int = 10_000_000_000) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


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
        return ", ".join(parts) if parts else description[:200]
    return description[:200]
