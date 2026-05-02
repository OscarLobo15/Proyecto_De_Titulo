OPTIONS = {
    "projectTypes": [
        {"value": "web", "label": "Web app"},
        {"value": "api", "label": "API backend"},
        {"value": "fullstack", "label": "Fullstack"},
    ],
    "projectProfiles": [
        {"value": "standard", "label": "Esqueleto web estandar"},
        {"value": "ai", "label": "Aplicacion con IA"},
        {"value": "microservices", "label": "Aplicacion con microservicios"},
        {"value": "api-only", "label": "API / agente backend"},
    ],
    "frontend": [{"value": "react", "label": "React + Vite"}],
    "backend": [{"value": "fastapi", "label": "FastAPI"}],
    "auth": [
        {"value": "firebase", "label": "Firebase Auth"},
        {"value": "none", "label": "Sin autenticacion"},
    ],
    "database": [
        {"value": "postgresql", "label": "PostgreSQL"},
        {"value": "firestore", "label": "Firestore"},
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
        {"value": "database", "label": "Base de datos"},
        {"value": "services", "label": "Servicios adicionales"},
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
