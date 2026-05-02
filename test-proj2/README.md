# Test Proj2

Proyecto generado desde arquitectura base.

Proyecto base generado con arquitectura parametrizable.

## Stack seleccionado

- Tipo: fullstack
- Perfil base: standard
- Frontend: react
- Backend: fastapi
- Autenticacion: firebase
- Base de datos: postgresql
- Cloud objetivo: Local Docker
- Contenedores: frontend, backend, database

## Requisitos

- Node.js 20+
- Python 3.12+
- Docker y Docker Compose, si usaras contenedores

## Ejecucion local

```bash
cp .env.example .env

chmod +x dev.sh
./dev.sh start

```

URLs:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs

## Docker

```bash
docker compose up --build
```

## Estructura

```txt
test-proj2/
├── frontend/
├── backend/


├── docker-compose.yml
├── dev.sh
├── setup.sh

├── package.json
└── .env.example
```



## Variables de entorno

Revisa `.env.example` y completa las credenciales necesarias antes de conectar servicios reales.


## Despliegue local

El objetivo cloud seleccionado es local, por lo que `docker compose up --build` es el camino recomendado para validar la arquitectura completa.


## Proximos pasos

- Reemplazar servicios mock por integraciones reales.
- Completar credenciales de autenticacion y base de datos.
- Agregar pruebas de dominio.
- Ajustar pipelines de CI/CD segun el cloud objetivo.
