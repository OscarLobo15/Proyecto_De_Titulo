OPTIONS = {
    "projectTypes": [
        {"value": "web", "label": "Web app", "description": "Frontend React + Vite sin backend propio; ideal para dashboards y apps estáticas."},
        {"value": "api", "label": "API backend", "description": "API REST con FastAPI y Swagger; endpoints documentados sin interfaz de usuario."},
        {"value": "fullstack", "label": "Fullstack", "description": "Frontend y backend integrados comunicados por API interna; paquete de proyecto completo."},
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
    "frontend": [{"value": "react", "label": "React + Vite", "description": "Biblioteca UI con Vite como bundler; hot reload, rutas con React Router y build optimizado."}],
    "backend": [{"value": "fastapi", "label": "FastAPI + Uvicorn", "description": "Framework Python moderno con tipado automático, Swagger integrado y servidor ASGI Uvicorn."}],
    "auth": [
        {"value": "firebase", "label": "Firebase Auth", "description": "Google Firebase: login social, email/contraseña, JWT y gestión de sesiones integrada."},
        {"value": "supabase", "label": "Supabase Auth", "description": "Supabase Auth: email, OAuth y control de acceso a nivel de fila (RLS) junto a la base de datos."},
        {"value": "none", "label": "Sin autenticacion", "description": "Sin módulo de autenticación; adecuado para APIs internas o prototipos sin login."},
    ],
    "database": [
        {"value": "postgresql", "label": "PostgreSQL", "description": "Base de datos relacional SQL; ideal para datos estructurados y transacciones complejas."},
        {"value": "firestore", "label": "Firestore", "description": "NoSQL de Firebase con sincronización en tiempo real y escalado automático gestionado."},
        {"value": "supabase", "label": "Supabase", "description": "PostgreSQL gestionado con API REST automática y autenticación incorporada en el mismo servicio."},
        {"value": "none", "label": "Sin base de datos", "description": "Sin base de datos; útil para servicios stateless o que consumen APIs externas."},
    ],
    "cloud": [
        {"value": "local", "label": "Local Docker", "description": "Docker Compose en máquina local; sin dependencia de nube, ideal para desarrollo y demos."},
        {"value": "gcp", "label": "GCP Cloud Run", "description": "Google Cloud Run: contenedores serverless que escalan automáticamente en GCP."},
        {"value": "aws", "label": "AWS App Runner / ECS", "description": "AWS App Runner o ECS: despliegue gestionado y escalable en la nube de Amazon."},
        {"value": "azure", "label": "Azure Container Apps", "description": "Azure Container Apps: contenedores con auto-escala en la infraestructura de Microsoft."},
    ],
    "containers": [
        {"value": "frontend", "label": "Frontend", "description": "Contenedor Nginx que sirve el build optimizado de React."},
        {"value": "backend", "label": "Backend", "description": "Contenedor Python con FastAPI y Uvicorn como servidor ASGI."},
        {"value": "services", "label": "Servicios adicionales", "description": "Contenedores independientes para cada microservicio adicional del proyecto."},
    ],
    "serviceCounts": [
        {"value": 0, "label": "Sin servicios extra", "description": "Solo frontend y backend principal; estructura mínima sin contenedores adicionales."},
        {"value": 1, "label": "1 servicio", "description": "Un servicio independiente; apropiado para un módulo de IA o de notificaciones."},
        {"value": 2, "label": "2 servicios", "description": "Dos servicios paralelos; por ejemplo, agente IA más procesamiento de archivos."},
        {"value": 3, "label": "3 servicios", "description": "Tres servicios; arquitectura modular con dominios de negocio claramente separados."},
        {"value": 4, "label": "4 servicios", "description": "Cuatro servicios; se recomienda un API Gateway para orquestar las llamadas entre ellos."},
        {"value": 5, "label": "5 servicios", "description": "Cinco servicios; arquitectura distribuida completa con múltiples dominios de negocio."},
    ],
    "targetOs": [
        {"value": "mac", "label": "macOS / Linux", "description": "Scripts Bash compatibles con macOS y distribuciones Linux (Ubuntu, Debian)."},
        {"value": "windows", "label": "Windows PowerShell", "description": "Scripts PowerShell optimizados para entornos Windows 10 y Windows 11."},
        {"value": "both", "label": "Ambos (macOS + Windows)", "description": "Genera tanto el script Bash (.sh) como el PowerShell (.ps1) de forma simultánea."},
    ],
    "navigationLayouts": [
        {"value": "sidebar", "label": "Sidebar", "description": "Navegación lateral persistente, alineada a paneles administrativos y consolas operativas."},
        {"value": "navbar", "label": "Navbar", "description": "Navegación horizontal superior, útil para productos más livianos y vistas de usuario final."},
    ],
    "loginVariants": [
        {"value": "ibm-classic", "label": "Editorial", "description": "Pantalla limpia tipo IBM/Carbon con bloque editorial y formulario sobrio."},
        {"value": "digital-workers", "label": "Operations console", "description": "Acceso oscuro con foco operacional, pensado para equipos internos y consolas de trabajo."},
        {"value": "digital-buyers", "label": "Client portal", "description": "Acceso luminoso y más comercial para productos orientados a clientes o autoservicio."},
    ],
    "experienceModes": [
        {"value": "admin", "label": "Admin directo", "description": "Después del login entra directo al panel operativo o consola administrativa."},
        {"value": "user", "label": "Portal + admin", "description": "Después del login entra al portal principal y el panel admin queda como acceso secundario."},
    ],
    "adminStyles": [
        {"value": "operations", "label": "Operations workspace", "description": "Panel oscuro y más denso, con navegación lateral tipo consola operativa."},
        {"value": "business", "label": "Business control", "description": "Panel claro y más ejecutivo, con estructura tipo portal administrativo."},
    ],
    "pages": [
        {"value": "login", "label": "Login"},
        {"value": "workspace", "label": "Workspace"},
        {"value": "settings", "label": "Settings"},
        {"value": "not-found", "label": "NotFound"},
    ],
    "serviceSkeletons": [
        {"value": "fastapi-service", "label": "Microservicio FastAPI base"},
        {"value": "agent-service", "label": "Servicio agente FastAPI"},
    ],
}
