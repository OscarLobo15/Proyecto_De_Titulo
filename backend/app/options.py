OPTIONS = {
    "projectTypes": [
        {"value": "web", "label": "Web app"},
        {"value": "api", "label": "API backend"},
        {"value": "fullstack", "label": "Fullstack"},
    ],
    "projectProfiles": [
        {
            "value": "standard",
            "label": "Producto modular",
            "description": "Base limpia con Home, panel principal y cinco modulos vacios para prototipos IBM.",
        },
        {
            "value": "ai",
            "label": "Producto con IA",
            "description": "Activa LangGraph en backend y agrega modulo Agente con chat e historial lateral.",
        },
        {
            "value": "microservices",
            "label": "Microservicios",
            "description": "Deriva services/ y contenedores adicionales; recomendado para integraciones separadas.",
        },
        {
            "value": "api-only",
            "label": "API / agente backend",
            "description": "Prioriza FastAPI, Swagger, salud, variables y conectores sin UI.",
        },
    ],
    "frontend": [{"value": "react", "label": "React + Vite"}],
    "backend": [{"value": "fastapi", "label": "FastAPI + Uvicorn"}],
    "auth": [
        {"value": "firebase", "label": "Firebase Auth"},
        {"value": "supabase", "label": "Supabase Auth"},
        {"value": "none", "label": "Sin autenticacion"},
    ],
    "database": [
        {"value": "postgresql", "label": "PostgreSQL"},
        {"value": "firestore", "label": "Firestore"},
        {"value": "supabase", "label": "Supabase"},
        {"value": "none", "label": "Sin base de datos"},
    ],
    "cloud": [
        {"value": "local", "label": "Local Docker"},
        {"value": "gcp", "label": "GCP Cloud Run"},
        {"value": "aws", "label": "AWS App Runner / ECS"},
        {"value": "azure", "label": "Azure Container Apps"},
    ],
    "containers": [
        {"value": "frontend", "label": "Frontend"},
        {"value": "backend", "label": "Backend"},
        {"value": "services", "label": "Servicios adicionales"},
    ],
    "serviceCounts": [
        {"value": 0, "label": "Sin servicios extra"},
        {"value": 1, "label": "1 servicio"},
        {"value": 2, "label": "2 servicios"},
        {"value": 3, "label": "3 servicios"},
        {"value": 4, "label": "4 servicios"},
        {"value": 5, "label": "5 servicios"},
    ],
    "targetOs": [
        {"value": "mac", "label": "macOS / Linux"},
        {"value": "windows", "label": "Windows PowerShell"},
        {"value": "both", "label": "Ambos (macOS + Windows)"},
    ],
    "pages": [
        {"value": "home", "label": "Home"},
        {"value": "login", "label": "Login"},
        {"value": "dashboard", "label": "Dashboard"},
        {"value": "settings", "label": "Settings"},
        {"value": "not-found", "label": "NotFound"},
    ],
    "serviceSkeletons": [
        {"value": "fastapi-service", "label": "Microservicio FastAPI base"},
        {"value": "agent-service", "label": "Servicio agente FastAPI"},
    ],
}
