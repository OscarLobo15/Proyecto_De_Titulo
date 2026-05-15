# Reference Architecture Generator — IBM Consulting Chile

Plataforma web para generar arquitecturas base reutilizables y estandarizadas para proyectos tecnológicos, con integración completa de **IBM Method Workspace** para planificación de delivery.

El sistema permite dos flujos: configuración manual parametrizable y generación asistida por IA que, a partir de una descripción en lenguaje natural, selecciona la arquitectura técnica, genera el proyecto como ZIP descargable, y produce un **plan de delivery IBM completo** con método recomendado, equipo, WBS, user stories, ADRs y estimación de costos CLP.

---

## Stack técnico

| Capa | Tecnologías |
|---|---|
| Frontend | React 18, Vite, React Router DOM, Axios, Lucide React |
| Backend | FastAPI, Uvicorn, Pydantic v2, Jinja2, Zipfile |
| IA / Orquestación | LangGraph (StateGraph), HTTPX, LLM remoto vía Cloudflare Tunnel |
| Estilos | IBM Carbon Design System (CSS custom, tokens de diseño IBM) |
| Infraestructura | Docker Compose, scripts `dev.sh` / `dev.ps1` |

---

## Ejecución local

```bash
./dev.sh start
```

Comandos disponibles:

```bash
./dev.sh stop
./dev.sh restart
./dev.sh status
./dev.sh backend     # solo backend
./dev.sh frontend    # solo frontend
./dev.sh logs
```

Variables de entorno — copiar `.env.example` a `.env` y ajustar:

```bash
AI_SERVER_URL=https://tu-tunnel.trycloudflare.com
AI_GENERATE_ENDPOINT=/generate
AI_TIMEOUT_SECONDS=300
```

## Docker

```bash
docker compose up --build
```

---

## Arquitectura del sistema de IA

El frontend no llama al LLM directamente. Todo el procesamiento IA ocurre en el backend:

```
Frontend React
  └─► POST /api/ai/analyze-project    → Grafo de análisis    → ProjectAnalysis
  └─► POST /api/ai/generate-project   → Grafo de generación  → ZIP descargable
  └─► POST /api/ai/plan-project       → Grafo de planificación IBM → IBMProjectPlan
                                                    ↓
                                        LangGraph StateGraph
                                                    ↓
                                        RemoteLLMClient (HTTPX)
                                                    ↓
                                        Servidor LLM remoto (Ollama/FastAPI)
```

La URL del modelo se configura solo en el backend. Si Cloudflare genera otra URL, cambiar `AI_SERVER_URL` y reiniciar el backend.

---

## Endpoints de la API

### `GET /health`
```json
{ "status": "ok" }
```

### `GET /options`
Retorna todas las opciones disponibles para el configurador manual (tipos de proyecto, stacks, cloud, etc.).

### `POST /generate`
Genera un ZIP desde configuración explícita. Body: `ProjectConfig`.

### `POST /api/ai/analyze-project`
Analiza requerimientos en lenguaje natural y retorna el stack técnico recomendado.

```bash
curl -X POST http://localhost:8000/api/ai/analyze-project \
  -H "Content-Type: application/json" \
  -d '{"message": "Plataforma de reservas con usuarios, autenticación, calendario y dashboard"}'
```

```json
{
  "success": true,
  "analysis": {
    "project_type": "fullstack",
    "frontend": "react",
    "backend": "fastapi",
    "database": "postgresql",
    "auth": "firebase",
    "deployment": "local",
    "required_modules": ["reservas", "calendario", "dashboard"],
    "recommended_templates": ["frontend-react", "backend-fastapi", "docker"],
    "notes": "..."
  }
}
```

### `POST /api/ai/generate-project`
Genera la arquitectura completa y retorna un ZIP descargable. La IA decide el stack; el generador renderiza templates controlados. Si la IA produce una arquitectura inválida, el backend aplica defaults seguros.

```bash
curl -X POST http://localhost:8000/api/ai/generate-project \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "psico-reservas",
    "prompt": "Plataforma de reservas psicológicas con pacientes, psicólogos, admin, autenticación, calendario, dashboard, PostgreSQL, Docker, GCP."
  }'
```

```json
{
  "success": true,
  "project_name": "psico-reservas",
  "selected_architecture": {
    "project_type": "fullstack",
    "frontend": "react",
    "backend": "fastapi",
    "database": "postgresql",
    "auth": "firebase",
    "cloud": "gcp"
  },
  "selected_templates": ["base", "frontend-react", "backend-fastapi", "auth-firebase", "docker", "cloud-gcp"],
  "download_url": "http://localhost:8000/download/psico-reservas.zip",
  "install_command": "curl -fsSL \"http://localhost:8000/install/...\" | bash"
}
```

### `POST /api/ai/plan-project`
**Nuevo.** Genera un plan de delivery IBM completo usando IBM Method Workspace como fuente de conocimiento. Produce método recomendado, equipo, WBS, user stories, ADRs y estimación de costos CLP.

```bash
curl -X POST http://localhost:8000/api/ai/plan-project \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "psico-reservas",
    "description": "Plataforma de reservas psicológicas con pacientes, psicólogos y administrador. Autenticación Firebase, PostgreSQL, Docker, despliegue en GCP.",
    "selected_architecture": {
      "project_type": "fullstack",
      "frontend": "react",
      "backend": "fastapi",
      "database": "postgresql",
      "auth": "firebase",
      "cloud": "gcp"
    }
  }'
```

Ver estructura completa de respuesta en la sección **IBM Method Workspace** más abajo.

### `GET /install/{token}`
Retorna un bash script que descarga el ZIP y levanta el proyecto. Se ejecuta con:
```bash
curl -fsSL "http://localhost:8000/install/{token}" | bash
```

### `GET /install/{token}/ps1`
Equivalente PowerShell para Windows.

### `GET /download/{file_name}`
Descarga directa del ZIP generado.

---

## IBM Method Workspace — Integración completa

### Fuente de conocimiento

El sistema integra el catálogo oficial de **IBM Method Workspace** como conocimiento embebido en los prompts del LLM. El agente razona autónomamente para seleccionar el método apropiado — no usa reglas hardcodeadas.

Fuente: `https://methodworkspace-prod.methodworkspace.dal.app.cirrus.ibm.com`  
Explorado: Home, Find Content (Methods, Work Practices, Work Products, Templates, Roles, Glossary), My Methods, Get Guidance, Methods Usage, Methods Catalogue.

### Catálogo de métodos integrados (37 métodos, 7 Service Lines)

| Service Line | Métodos |
|---|---|
| **CSLM** | IBM Services Mosaic, Solutioning, Team Solution Design, WWPgMM, WWPMM Agile, WWPMM Traditional |
| **AOP** | Application IMPACT Maintenance/QE/Transition, IBM DevSecOps and AIOps, Platform Services Delivery |
| **BAP** | Enterprise SAP Transformation, IBM Ascend SAP/SuccessFactors, Oracle On-Premise/Cloud, Salesforce, Adobe, Workday |
| **BOP** | BPO Transition, Content Intelligence, Customer Care, Garage Method for Automation, Service Transformation |
| **CSS** | Cyber Strategy and Risk [NEW], Cyber Threat Management, CyberDefend |
| **HCD** | AI Integration, Agentic Method for App Migration, AD-Agile, AD-Waterfall, Application Move & Modernization, Data Governance [NEW], Data Transformation, IBM Ascend Microsoft, IBM Garage Method for Cloud, Scaled Data Science |
| **STR** | BPM, Commerce, Connected Solutions, Experience Strategy & Design, Finance Transformation, IBM Change, Maximo, Package Implementation, Supply Chain [NEW], Talent Transformation |

### Lógica de selección autónoma del agente

El LLM recibe el catálogo completo y decide según señales del proyecto:

| Si el proyecto tiene... | El agente selecciona |
|---|---|
| LLM, LangGraph, agentes, Watson, chatbot | AI Integration (HCD) |
| ML, scikit-learn, PyTorch, Jupyter, MLOps | Scaled Data Science (HCD) |
| ETL, dbt, Spark, pipelines de datos | Data Transformation (HCD) |
| GDPR, master data, data catalog, compliance | Data Governance (HCD) |
| CI/CD, DevOps, platform engineering, AIOps | IBM DevSecOps and AIOps (AOP) |
| Modernización de legacy, microservicios | Agentic Method (HCD) |
| SAP cualquier módulo | Enterprise SAP Transformation (BAP) |
| Salesforce CRM/Sales/Service | IBM Salesforce Engagement (BAP) |
| Workday HCM/Finance | Workday (BAP) |
| RPA, UiPath, Automation Anywhere | Garage Method for Automation (BOP) |
| Ciberseguridad, zero trust, SIEM, SOC | Cyber Strategy and Risk (CSS) |
| UX research, design system | Experience Strategy & Design (STR) |
| Mantenimiento steady-state | Application IMPACT Maintenance (AOP) |
| App web/API/fullstack sin IA pesada | AD-Agile (HCD) |
| Scope fijo, ERP custom, regulatorio | AD-Waterfall (HCD) |
| Multi-equipo, PMO, programa complejo | WWPMM Agile (CSLM) |

### Estructura del plan generado (`IBMProjectPlan`)

```json
{
  "ibm_recommended_method": "Application Development - Agile (AD-Agile)",
  "ibm_method_rationale": "Justificación 2-3 oraciones específicas al proyecto",
  "service_line": "HCD - Hybrid Cloud & Data",
  "project_overview": "Descripción desde perspectiva IBM Consulting",
  "adoption_journey": "Delivery",
  "tailoring_notes": "Cómo se adaptó el método estándar a este engagement",

  "team_roles": [
    {
      "role_name": "Project Manager",
      "ibm_method_workspace_role": "Client Project Manager",
      "seniority": "Senior",
      "phase": "All",
      "dedication_weeks": 21,
      "monthly_rate_clp": 7000000,
      "justification": "Gestión del engagement y coordinación con cliente"
    }
  ],

  "wbs_phases": [
    {
      "phase_name": "Iteration 0",
      "ibm_method_phase": "Iteration 0",
      "duration_weeks": 3,
      "objectives": ["Setup del proyecto", "Definición de arquitectura"],
      "tasks": [
        { "task": "Definición de arquitectura base", "responsible_role": "Solution Architect", "effort_days": 5 }
      ],
      "deliverables": ["Architecture Overview Document", "Development Environment"]
    }
  ],

  "user_stories": [
    {
      "id": "US-001",
      "epic": "Acceso y Seguridad",
      "as_a": "usuario registrado",
      "i_want": "iniciar sesión de forma segura",
      "so_that": "pueda acceder al sistema",
      "acceptance_criteria": ["Autentica en <2s", "Bloquea tras 5 intentos", "Sesión expira en 30min"],
      "priority": "Must Have",
      "story_points": 5
    }
  ],

  "architecture_decisions": [
    {
      "id": "ADR-001",
      "title": "Adopt React + Vite for Frontend",
      "status": "Accepted",
      "context": "El proyecto requiere un frontend moderno...",
      "decision": "Usar React 18 con Vite como build tool",
      "rationale": "React es el framework preferido de IBM Consulting...",
      "alternatives_considered": ["Angular — rechazado por mayor curva de aprendizaje"],
      "consequences": "Beneficios del ecosistema React. Requiere disciplina en arquitectura de componentes."
    }
  ],

  "cost_estimate": {
    "currency": "CLP",
    "project_duration_months": 6,
    "roles_breakdown": [
      { "role_name": "Project Manager", "seniority": "Senior", "monthly_rate_clp": 7000000, "duration_months": 4.8, "total_clp": 33600000 }
    ],
    "total_project_cost_clp": 185000000,
    "setup_cost_without_solution_clp": 42000000,
    "setup_cost_with_solution_clp": 18900000,
    "estimated_savings_clp": 23100000,
    "savings_percentage": 55.0,
    "methodology_note": "Estimación basada en tarifas IBM Consulting Chile 2025..."
  },

  "project_risks": ["Riesgo específico al stack/dominio del proyecto"],
  "ibm_assets_recommended": ["Architecture Overview Document", "Acceptance Test Plan"]
}
```

### Roles IBM MW integrados (16 roles exactos)

| Rol IBM MW | Tarifa mensual CLP |
|---|---|
| Business Sales & Delivery Leader: Associate Partner | $11.000.000 |
| Application Architect: Hybrid Cloud | $8.500.000 |
| Automation Architect | $7.500.000 |
| Client Project Manager | $7.000.000 |
| Cloud Build Platform Architect | $6.500.000 |
| Application Developer: DevOps | $6.000.000 |
| Agile Coach | $5.500.000 |
| Application Developer (Senior) / Business Analyst (Senior) | $5.000.000 |
| Application Architect: Quality Engineering | $4.500.000 |
| Application Developer (Mid) / Business Analyst (Mid) | $3.500.000 |
| Application Developer (Junior) | $2.500.000 |

### Adoption Journey

El agente determina automáticamente si el engagement es:
- **Delivery Journey** — proyecto activo de entrega para un cliente
- **Solutioning Journey** — contexto de pre-venta, propuesta o RFP

### Modelo de ahorro (tesis)

El costo de setup inicial (primeras 4 semanas de todo el equipo) se calcula con y sin la plataforma generadora. La plataforma reduce el setup en ~55%, pasando de semanas manuales de configuración a un ZIP listo en minutos. Este diferencial es el argumento cuantificable de valor del proyecto de tesis.

---

## Grafo LangGraph — `project_planning_graph.py`

```
receive_plan_request
       ↓
generate_method_and_team    [LLM call 1 — catálogo IBM MW completo, 37 métodos]
       ↓
generate_user_stories        [LLM call 2 — formato AD-Agile, MoSCoW, Fibonacci]
       ↓
generate_architecture_decisions  [LLM call 3 — formato IBM ADR]
       ↓
compute_cost_estimate        [Python puro — tarifas CLP, cálculo de ahorro]
       ↓
assemble_plan                [Python puro — arma IBMProjectPlan]
       ↓
      END
```

Cada nodo tiene fallback en Python para cuando el LLM falla o retorna JSON inválido. Los parsers son tolerantes: extraen JSON de respuestas imperfectas del modelo.

---

## Grafo LangGraph — `project_generation_graph.py`

```
receive_user_request
       ↓
analyze_requirements         [LLM + heurísticas]
       ↓
select_architecture
       ↓
select_templates
       ↓
validate_template_selection
       ↓
generate_project_config
       ↓
call_project_generator       [renderiza templates Jinja2]
       ↓
package_project              [genera ZIP]
       ↓
return_download_response
```

---

## Templates disponibles

| Directorio | Contenido |
|---|---|
| `templates/base/` | `dev.sh`, `dev.ps1`, `package.json`, `README.md`, `setup.sh`, `SETUP_GUIDE.md` |
| `templates/frontend-react/` | App React completa: rutas, layouts, contextos, servicios, estilos IBM Carbon |
| `templates/backend-fastapi/` | FastAPI: modelos, rutas, schemas, servicios, tests de salud |
| `templates/docker/` | `Dockerfile` frontend y backend, `docker-compose.yml` |
| `templates/auth-firebase/` | Integración Firebase Auth |
| `templates/cloud-aws/` | Scripts de despliegue AWS + documentación |
| `templates/cloud-azure/` | Scripts de despliegue Azure + documentación |
| `templates/cloud-gcp/` | `cloudbuild.yaml`, scripts GCP + documentación |
| `templates/services/` | Microservicio base (Dockerfile, FastAPI, requirements) |

---

## Estructura del proyecto

```
Proyecto_De_Titulo/
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   │   ├── project_analysis_graph.py     # Grafo análisis de requerimientos
│   │   │   ├── project_generation_graph.py   # Grafo generación ZIP
│   │   │   └── project_planning_graph.py     # Grafo planificación IBM MW ← nuevo
│   │   ├── services/
│   │   │   └── ai_client.py                  # RemoteLLMClient (HTTPX + retry)
│   │   ├── config.py                         # Settings desde .env
│   │   ├── generator.py                      # Motor de templates Jinja2 + ZIP
│   │   ├── main.py                           # FastAPI app + todos los endpoints
│   │   ├── models.py                         # Todos los modelos Pydantic
│   │   └── options.py                        # Opciones del configurador manual
│   └── scripts/
│       └── test_ai_generation_flow.py        # Script de prueba local
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ArchitecturePreview.jsx
│       │   ├── IBMProjectPlanView.jsx         # Vista plan IBM ← nuevo
│       │   ├── LiveProjectPreview.jsx
│       │   ├── OptionCard.jsx
│       │   └── StepHeader.jsx
│       ├── pages/
│       │   └── GeneratorPage.jsx             # Página principal con flujo AI de 5 pasos
│       ├── services/
│       │   └── api.js                        # Axios: analyze, generate, plan ← actualizado
│       └── styles/
│           └── index.css                     # IBM Carbon Design System CSS
├── templates/                                # Templates Jinja2 por categoría
├── context/
│   └── guia_desarrollo_plataforma_generadora.md
├── docs/
│   └── REFERENCE_PROJECTS.md
├── dev.sh / dev.ps1                          # Runner local cross-platform
├── docker-compose.yml
└── .env.example
```

---

## Flujo completo del modo IA (5 pasos)

```
Paso 1 — Generación
  El usuario describe el proyecto en lenguaje natural.
  La IA analiza y genera: stack técnico, módulos, roles, navegación, ZIP descargable.

Paso 2 — Review
  Resumen estructurado de la arquitectura propuesta: tipo, frontend, backend, DB, auth, cloud.
  Módulos y roles detectados. Templates aplicados.

Paso 3 — Plan IBM  ← nuevo
  El agente consulta el catálogo IBM Method Workspace (37 métodos).
  Genera automáticamente:
    · Método IBM recomendado + justificación + service line + adoption journey
    · Equipo de delivery con roles exactos IBM MW y tarifas CLP
    · WBS con fases del método seleccionado, tareas y entregables
    · 8-12 User Stories en formato AD-Agile (As-a/I-want/So-that, MoSCoW, Fibonacci)
    · 4-6 Architecture Decision Records (ADR) formato IBM
    · Estimación de costos CLP con modelo de ahorro del proyecto de tesis

Paso 4 — Vista previa
  Preview navegable del MVP generado (solo proyectos con frontend).
  Panel de personalización visual: módulos, roles, navegación, login.

Paso 5 — Entrega
  Opciones finales: Docker, dev script, OS target.
  Comando de instalación reproducible (bash / PowerShell).
```

---

## CLI local

Con el backend levantado:

```bash
npm link
create-reference-architecture
```

El CLI consulta nombre, perfil, auth, base de datos, cloud y servicios opcionales. Luego crea la carpeta del proyecto e instala las dependencias cuando se usa `--install`.

---

## Script de prueba IA

```bash
# Sin LLM remoto (heurísticas locales)
cd backend
../.venv/bin/python scripts/test_ai_generation_flow.py

# Con LLM remoto configurado
cd backend
../.venv/bin/python scripts/test_ai_generation_flow.py --remote
```


## Stack

- Frontend: React, Vite, React Router DOM y Axios.
- Backend: FastAPI, Pydantic, Jinja2, Zipfile, LangGraph y HTTPX.
- Generación: templates parametrizables para React, FastAPI, Docker, README, variables de entorno y scripts locales.
- IA: orquestador LangGraph en backend conectado a un LLM remoto Ollama/FastAPI por Cloudflare Tunnel.

## Ejecución local

```bash
./dev.sh start
```

Comandos disponibles:

```bash
./dev.sh stop
./dev.sh restart
./dev.sh status
./dev.sh backend
./dev.sh frontend
./dev.sh logs
```

El runner sigue el patrón de los proyectos de referencia: `.venv` en la raíz, instalación automática por cambios en dependencias, logs en `/tmp`, PID files y health checks.

## Docker

```bash
docker compose up --build
```

## Capa IA con LangGraph

El frontend no llama al servidor LLM remoto. El flujo queda encapsulado asi:

```text
Frontend React -> Backend FastAPI -> LangGraph -> Servicio LLM remoto -> ProjectConfig -> ProjectGenerator -> ZIP -> Frontend
```

La URL del modelo se configura solo en el backend. Copia `.env.example` a `.env` y ajusta:

```bash
AI_SERVER_URL=https://variations-suited-tile-survey.trycloudflare.com
AI_GENERATE_ENDPOINT=/generate
AI_TIMEOUT_SECONDS=300
```

Si Cloudflare genera otra URL, cambia solo `AI_SERVER_URL` y reinicia el backend. El endpoint remoto esperado es:

```http
POST /generate
Content-Type: application/json

{
  "prompt": "texto del usuario"
}
```

Respuesta esperada del servidor remoto:

```json
{
  "response": "respuesta del modelo"
}
```

### Endpoint local de analisis

Con el backend levantado:

```bash
curl -X POST http://127.0.0.1:8000/api/ai/analyze-project \
  -H "Content-Type: application/json" \
  -d '{"message":"Necesito una plataforma de reservas con usuarios, autenticacion, calendario y dashboard administrativo"}'
```

Respuesta del backend:

```json
{
  "success": true,
  "analysis": {
    "project_type": "fullstack",
    "frontend": "React + Vite",
    "backend": "FastAPI",
    "database": "PostgreSQL",
    "auth": "Firebase Auth",
    "deployment": "Docker local inicialmente; Cloud Run si se publica MVP",
    "required_modules": ["usuarios", "reservas", "calendario", "dashboard administrativo"],
    "recommended_templates": ["frontend-react", "backend-fastapi", "docker"],
    "notes": "Observaciones tecnicas breves."
  }
}
```

### Endpoint de generacion con IA

Este endpoint usa IA para tomar decisiones, pero el resultado final lo construye el motor de templates controlado del backend.

```bash
curl -X POST http://127.0.0.1:8000/api/ai/generate-project \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "psico-reservas",
    "prompt": "Necesito una plataforma web para gestion de reservas psicologicas. Debe tener pacientes, psicologos, administrador, autenticacion, calendario de disponibilidad, reservas, dashboard, PostgreSQL, Docker y despliegue cloud."
  }'
```

Respuesta:

```json
{
  "success": true,
  "project_name": "psico-reservas",
  "selected_architecture": {
    "project_type": "fullstack",
    "frontend": "react",
    "backend": "fastapi",
    "database": "postgresql",
    "auth": "firebase",
    "include_docker": true,
    "cloud": "gcp"
  },
  "selected_templates": ["base", "frontend-react", "backend-fastapi", "auth-firebase", "docker", "cloud-gcp"],
  "download_url": "http://127.0.0.1:8000/download/psico-reservas.zip",
  "file_name": "psico-reservas.zip",
  "install_command": "curl -fsSL \"http://127.0.0.1:8000/install/...\" | bash",
  "install_command_windows": null,
  "message": "Proyecto generado correctamente"
}
```

Los templates seleccionados son grupos reales dentro de `templates/`. La IA no escribe codigo arbitrario; LangGraph normaliza la salida del LLM a una configuracion `ProjectConfig` y `ProjectGenerator` renderiza los templates existentes. Si la IA sugiere una arquitectura invalida, el backend aplica defaults seguros o responde con un error claro si falta una plantilla critica.

### Script de prueba IA

Prueba local sin depender del tunnel remoto:

```bash
cd backend
../.venv/bin/python scripts/test_ai_generation_flow.py
```

Prueba usando el LLM remoto configurado:

```bash
cd backend
../.venv/bin/python scripts/test_ai_generation_flow.py --remote
```

### Decisiones de arquitectura

- La capa IA vive en `backend/app/ai` y `backend/app/services`, separada del generador actual para no mezclar la logica de ZIP/templates con analisis inteligente.
- `RemoteLLMClient` lee URL, endpoint y timeout desde variables de entorno, valida la respuesta remota y centraliza errores de red.
- El grafo de analisis mantiene los nodos `receive_user_request`, `analyze_requirements`, `select_stack` y `generate_project_plan`.
- El grafo de generacion usa `receive_user_request`, `analyze_requirements`, `select_architecture`, `select_templates`, `validate_template_selection`, `generate_project_config`, `call_project_generator`, `package_project` y `return_download_response`.
- El backend valida que la salida del modelo sea JSON parseable con el contrato esperado antes de responder al frontend.
- El flujo queda preparado para sumar upload de PCR/PDF, extraccion avanzada de requerimientos, seleccion fina de modulos y generacion de codigo descargable.

## Flujo MVP

1. Configurar el proyecto desde la web.
2. Enviar la configuración a `POST /generate`.
3. Copiar el comando npm generado.
4. Ejecutar el comando para crear e instalar el esqueleto.
5. Levantar el proyecto con `./dev.sh start` o `docker compose up --build`.

## CLI local

Con el backend levantado:

```bash
npm link
create-reference-architecture
```

El CLI consulta nombre, perfil, auth, base de datos, cloud y servicios opcionales. Luego crea la carpeta del proyecto e instala las dependencias cuando se usa `--install`.

## Criterios de estructura

La estructura generada sigue una convencion comun para proyectos fullstack: runner local en la raiz, frontend y backend separados, variables de entorno de ejemplo, health checks, scripts de setup, Docker opcional y servicios adicionales cuando el usuario los selecciona.
