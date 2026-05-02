# Criterios de estandarizacion

Este generador toma como base convenciones comunes de proyectos fullstack y backend: estructura modular, scripts repetibles, variables de entorno separadas y servicios opcionales.

## Patrones reutilizados

- `dev.sh` en la raiz con comandos `start`, `stop`, `restart`, `status`, `backend`, `frontend`, `logs`.
- `.venv` en la raiz para dependencias Python compartidas.
- `frontend/` y `backend/` separados.
- Health checks antes de reportar servicios listos.
- Logs locales en `/tmp`.
- PID files para detener procesos de forma consistente.
- `.env.example` y credenciales fuera del codigo.
- `services/` opcional para microservicios o agentes especializados.

## Perfiles iniciales

- `standard`: frontend React + backend FastAPI + Docker opcional.
- `ai`: base pensada para agentes o flujos con IA.
- `microservices`: incluye carpeta `services/template`.
- `api-only`: deja la configuracion orientada a backend.

## Alcance actual

El generador produce esqueletos limpios, mantenibles y parametrizables sin acoplarse a contenido de proyectos especificos.
