# Reference Architecture Generator

Plataforma web para generar arquitecturas base reutilizables y parametrizables para proyectos tecnológicos.

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
