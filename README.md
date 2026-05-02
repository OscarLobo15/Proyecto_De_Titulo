# Reference Architecture Generator

Plataforma web para generar arquitecturas base reutilizables y parametrizables para proyectos tecnológicos.

## Stack

- Frontend: React, Vite, React Router DOM y Axios.
- Backend: FastAPI, Pydantic, Jinja2 y Zipfile.
- Generación: templates parametrizables para React, FastAPI, Docker, README, variables de entorno y scripts locales.

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
