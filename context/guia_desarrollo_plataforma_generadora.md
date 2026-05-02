# Guía de desarrollo — Plataforma generadora de arquitecturas base

## 1. Contexto del proyecto

Este proyecto corresponde al desarrollo de una solución para el Proyecto de Título de Oscar Lobo, en el contexto de IBM Consulting Chile. La problemática identificada es que en proyectos tecnológicos del área de consulting existe una alta repetición de tareas técnicas y componentes arquitectónicos durante la etapa de configuración inicial o setup.

A partir del análisis de cinco proyectos tecnológicos, se identificó que entre un 60% y un 80% de los componentes arquitectónicos y tareas técnicas se repiten entre proyectos. Sin embargo, cada nuevo proyecto tiende a comenzar desde cero, lo que genera retrabajo, variabilidad técnica y tiempos elevados de configuración inicial, estimados entre 3 y 5 semanas por proyecto.

El objetivo del proyecto es reducir el tiempo promedio de setup desde aproximadamente 4 semanas a menos de 2 semanas, mediante el diseño e implementación de una arquitectura de referencia reutilizable y parametrizable. Esta arquitectura se materializará en una plataforma web generadora de proyectos base.

La solución debe permitir que un usuario configure los componentes técnicos de un nuevo proyecto y genere automáticamente una estructura funcional lista para desarrollo y despliegue.

---

## 2. Objetivo de la solución

Construir una plataforma web que permita generar proyectos tecnológicos base de manera parametrizable.

El usuario debe poder seleccionar, mediante una interfaz web:

- Tecnología frontend.
- Tecnología backend.
- Sistema de autenticación.
- Base de datos.
- Proveedor cloud objetivo.
- Cantidad y tipo de contenedores.
- Servicios adicionales.
- Nombre del proyecto.
- Estructura deseada del proyecto.

A partir de esa configuración, la plataforma debe generar automáticamente un proyecto descargable o instalable mediante comando npm, incluyendo frontend, backend, configuración Docker, scripts de ejecución, variables de entorno de ejemplo y documentación.

---

## 3. Stack tecnológico principal

La plataforma generadora debe desarrollarse con:

### Frontend de la plataforma

- React.
- Vite.
- React Router DOM.
- Axios.
- Tailwind CSS o CSS modular.
- Componentes reutilizables.
- Formularios controlados.
- Estructura limpia y mantenible.

### Backend de la plataforma

- Python.
- FastAPI.
- Pydantic.
- Uvicorn.
- Jinja2 o motor de templates para generación de archivos.
- Zipfile para empaquetar proyectos generados.
- Manejo de archivos y carpetas.
- API REST.

### Generador / CLI

La solución debe considerar un comando npm para generar proyectos.

Opciones posibles:

1. Crear un paquete npm tipo CLI:
   - Comando esperado: `npx create-ibm-architecture`
   - El CLI puede consultar al usuario por terminal o conectarse al backend generador.

2. Crear un generador descargable desde la web:
   - El usuario configura el proyecto en la web.
   - El backend genera un `.zip`.
   - El usuario descarga el proyecto.
   - El proyecto generado incluye un `package.json` y scripts npm para instalar y ejecutar.

Idealmente, implementar ambas posibilidades si el tiempo lo permite:
- MVP: generación desde web y descarga zip.
- Mejora posterior: CLI npm.

---

## 4. Funcionalidades principales de la plataforma

### 4.1 Configuración del proyecto

La plataforma debe permitir al usuario completar:

- Nombre del proyecto.
- Descripción breve.
- Tipo de proyecto:
  - Web app.
  - API backend.
  - Fullstack.
- Frontend:
  - React.
  - Next.js, opcional en versión futura.
- Backend:
  - FastAPI.
  - Node.js, opcional en versión futura.
- Autenticación:
  - Firebase Auth.
  - Sin autenticación.
  - Auth0, opcional futuro.
- Base de datos:
  - PostgreSQL.
  - Firestore.
  - MongoDB, opcional futuro.
  - Sin base de datos.
- Cloud objetivo:
  - GCP.
  - AWS.
  - Azure.
  - Local Docker.
- Contenedores:
  - Frontend.
  - Backend.
  - Base de datos.
  - Servicios adicionales.
- Configuración de despliegue:
  - Dockerfile frontend.
  - Dockerfile backend.
  - docker-compose.yml.
  - dev.sh.
  - .env.example.
- Páginas base del frontend:
  - Login.
  - Dashboard.
  - Home.
  - NotFound.
  - Perfil o Settings.
- Rutas:
  - Públicas.
  - Protegidas.
- Estructura de carpetas:
  - Separación de componentes.
  - Separación de servicios.
  - Separación de estilos.
  - Separación de páginas.
  - Separación de configuración.

---

## 5. Resultado esperado del proyecto generado

El proyecto generado debe quedar funcional desde el primer momento.

El usuario debería poder ejecutar algo como:

```bash
npm install
npm run dev
```

o, si el proyecto generado incluye frontend y backend:

```bash
./dev.sh
```

También debe poder levantar los contenedores con:

```bash
docker compose up --build
```

El proyecto generado debe incluir como mínimo:

```txt
generated-project/
├── README.md
├── package.json
├── docker-compose.yml
├── dev.sh
├── .env.example
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── index.html
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── routes/
│       │   ├── AppRouter.jsx
│       │   └── ProtectedRoute.jsx
│       ├── pages/
│       │   ├── Home.jsx
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx
│       │   ├── Settings.jsx
│       │   └── NotFound.jsx
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Header.jsx
│       │   │   ├── Sidebar.jsx
│       │   │   └── Layout.jsx
│       │   └── ui/
│       │       ├── Button.jsx
│       │       ├── Card.jsx
│       │       └── Input.jsx
│       ├── services/
│       │   ├── api.js
│       │   └── authService.js
│       ├── context/
│       │   └── AuthContext.jsx
│       ├── config/
│       │   └── firebase.js
│       └── styles/
│           ├── index.css
│           └── variables.css
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── app/
    │   ├── main.py
    │   ├── config.py
    │   ├── database.py
    │   ├── routes/
    │   │   ├── health.py
    │   │   ├── auth.py
    │   │   └── users.py
    │   ├── services/
    │   │   ├── auth_service.py
    │   │   └── user_service.py
    │   ├── models/
    │   │   └── user.py
    │   ├── schemas/
    │   │   └── user_schema.py
    │   └── utils/
    │       └── security.py
    └── tests/
        └── test_health.py
```

---

## 6. Arquitectura de la plataforma generadora

La plataforma que genera proyectos debe tener esta arquitectura:

```txt
architecture-generator/
├── frontend/
│   └── React app de configuración
├── backend/
│   └── FastAPI generator API
├── templates/
│   ├── frontend-react/
│   ├── backend-fastapi/
│   ├── auth-firebase/
│   ├── db-postgres/
│   ├── cloud-gcp/
│   ├── cloud-aws/
│   ├── cloud-azure/
│   └── docker/
├── generated/
│   └── proyectos generados temporalmente
├── docs/
│   └── documentación técnica
├── README.md
└── docker-compose.yml
```

---

## 7. Backend FastAPI de la plataforma generadora

El backend debe exponer una API REST.

### Endpoints mínimos

#### `GET /health`

Verifica que el backend esté activo.

Respuesta:

```json
{
  "status": "ok"
}
```

#### `GET /options`

Entrega las opciones disponibles para configurar el proyecto.

Respuesta esperada:

```json
{
  "frontend": ["react"],
  "backend": ["fastapi"],
  "auth": ["firebase", "none"],
  "database": ["postgresql", "firestore", "none"],
  "cloud": ["gcp", "aws", "azure", "local"],
  "containers": ["frontend", "backend", "database"]
}
```

#### `POST /generate`

Recibe la configuración del usuario y genera el proyecto.

Payload esperado:

```json
{
  "project_name": "mi-proyecto",
  "frontend": "react",
  "backend": "fastapi",
  "auth": "firebase",
  "database": "postgresql",
  "cloud": "gcp",
  "containers": ["frontend", "backend", "database"],
  "include_docker": true,
  "include_dev_script": true
}
```

Respuesta esperada:

```json
{
  "status": "success",
  "download_url": "/download/mi-proyecto.zip"
}
```

#### `GET /download/{file_name}`

Descarga el archivo zip generado.

---

## 8. Lógica del motor generador

El motor generador debe:

1. Recibir configuración del usuario.
2. Validar los datos con Pydantic.
3. Crear carpeta temporal del proyecto.
4. Copiar templates base según selección.
5. Reemplazar variables dinámicas:
   - nombre del proyecto.
   - puertos.
   - proveedor cloud.
   - configuración de auth.
   - configuración de base de datos.
6. Generar archivos:
   - README.md.
   - .env.example.
   - docker-compose.yml.
   - dev.sh.
   - package.json raíz.
7. Empaquetar en zip.
8. Entregar link de descarga.
9. Limpiar archivos temporales si corresponde.

---

## 9. Templates necesarios

Se deben crear templates reutilizables. Cada template debe ser simple, funcional y extensible.

### Template frontend React

Debe incluir:

- Vite.
- React Router.
- Login funcional base.
- AuthContext.
- ProtectedRoute.
- Dashboard.
- Layout.
- Header.
- Sidebar.
- Componentes UI básicos.
- Axios configurado.
- Variables de entorno.

### Template backend FastAPI

Debe incluir:

- FastAPI.
- Uvicorn.
- Rutas base.
- Health check.
- CORS.
- Configuración por variables de entorno.
- Estructura modular.
- Rutas separadas.
- Servicios separados.
- Schemas Pydantic.
- Conexión preparada a base de datos si corresponde.

### Template Firebase

Debe incluir:

- Archivo `firebase.js` en frontend.
- Variables en `.env.example`.
- Servicio de login/logout.
- Contexto de autenticación.
- Protección de rutas.

### Template Docker

Debe incluir:

- Dockerfile frontend.
- Dockerfile backend.
- docker-compose.yml.
- Configuración de puertos.
- Variables de entorno.
- Servicio de base de datos si aplica.

### Template Cloud

Para MVP se puede generar documentación y archivos base para despliegue en:

- GCP Cloud Run.
- AWS ECS o App Runner.
- Azure Container Apps.

Inicialmente, basta con generar instrucciones específicas en README según cloud seleccionada. Si hay tiempo, agregar archivos YAML o Terraform básicos.

---

## 10. CLI npm esperado

El proyecto debería aspirar a incluir un CLI npm.

### Nombre sugerido

```bash
create-reference-architecture
```

### Uso esperado

```bash
npx create-reference-architecture
```

El CLI debería preguntar:

```txt
Nombre del proyecto:
Selecciona frontend:
Selecciona backend:
Selecciona autenticación:
Selecciona base de datos:
Selecciona cloud:
Selecciona contenedores:
```

Luego debería generar el proyecto localmente.

### Alternativa MVP

Si no se alcanza a publicar en npm, se puede crear un CLI local dentro del repo:

```bash
npm link
create-reference-architecture
```

O ejecutar:

```bash
node cli/index.js
```

---

## 11. Flujo funcional de usuario

1. Usuario ingresa a la plataforma web.
2. Completa nombre del proyecto.
3. Selecciona stack técnico.
4. Selecciona autenticación.
5. Selecciona base de datos.
6. Selecciona cloud.
7. Selecciona contenedores.
8. Hace clic en “Generar proyecto”.
9. Backend crea la estructura.
10. Usuario descarga zip.
11. Usuario descomprime.
12. Usuario ejecuta:

```bash
chmod +x dev.sh
./dev.sh
```

o:

```bash
docker compose up --build
```

13. Proyecto base queda funcionando.

---

## 12. Criterios de aceptación del MVP

El MVP se considerará funcional si cumple con:

- La plataforma web permite seleccionar configuración técnica.
- El backend recibe y valida la configuración.
- El backend genera un proyecto base.
- El proyecto generado incluye frontend React funcional.
- El proyecto generado incluye backend FastAPI funcional.
- El proyecto generado incluye Dockerfile y docker-compose.
- El proyecto generado incluye dev.sh.
- El proyecto generado incluye README.md.
- El proyecto generado puede ejecutarse localmente.
- El proyecto generado respeta estructura modular.
- El proyecto generado incluye login si se selecciona Firebase.
- El proyecto generado permite iniciar desarrollo sin partir desde cero.

---

## 13. Buenas prácticas obligatorias

### Frontend

- Separar páginas, componentes, servicios, contexto y estilos.
- Usar nombres claros.
- No mezclar lógica de API dentro de componentes visuales.
- Centralizar llamadas HTTP en `services/api.js`.
- Centralizar autenticación en `AuthContext`.
- Usar rutas protegidas.
- Mantener layout reutilizable.

### Backend

- Separar rutas, servicios, schemas y configuración.
- Usar variables de entorno.
- Configurar CORS.
- Incluir endpoint `/health`.
- Incluir manejo básico de errores.
- Evitar lógica compleja dentro de `main.py`.

### Generador

- No hardcodear rutas innecesarias.
- Usar templates parametrizables.
- Validar configuraciones antes de generar.
- Manejar errores con mensajes claros.
- Evitar sobrescribir proyectos sin confirmación.
- Generar proyectos con nombres válidos.

---

## 14. Variables de entorno mínimas

### Plataforma generadora

```env
GENERATOR_ENV=development
BACKEND_PORT=8000
FRONTEND_PORT=5173
GENERATED_PROJECTS_DIR=generated
```

### Proyecto generado con Firebase

```env
VITE_API_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
```

### Proyecto generado con backend

```env
APP_ENV=development
API_PORT=8000
DATABASE_URL=
FIREBASE_PROJECT_ID=
```

---

## 15. Scripts esperados

### En la plataforma generadora

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Docker:

```bash
docker compose up --build
```

### En proyecto generado

```bash
npm install
npm run dev
```

o:

```bash
./dev.sh
```

o:

```bash
docker compose up --build
```

---

## 16. Archivo `dev.sh` esperado en proyecto generado

El archivo `dev.sh` debe permitir levantar frontend y backend en local.

Debe:

1. Verificar dependencias básicas.
2. Instalar dependencias si no existen.
3. Levantar backend FastAPI.
4. Levantar frontend React.
5. Mostrar URLs de acceso.

Ejemplo de comportamiento esperado:

```txt
Frontend: http://localhost:5173
Backend: http://localhost:8000
Swagger: http://localhost:8000/docs
```

---

## 17. README esperado del proyecto generado

Cada proyecto generado debe incluir un README con:

- Nombre del proyecto.
- Stack seleccionado.
- Estructura de carpetas.
- Requisitos previos.
- Instalación.
- Ejecución local.
- Ejecución con Docker.
- Configuración de variables de entorno.
- Despliegue según cloud seleccionada.
- Próximos pasos recomendados.

---

## 18. Roadmap de desarrollo recomendado

### Fase 1 — Preparación del repositorio

- Crear repositorio GitHub.
- Definir estructura base.
- Crear README inicial.
- Configurar `.gitignore`.
- Configurar frontend React.
- Configurar backend FastAPI.
- Configurar docker-compose de la plataforma generadora.

### Fase 2 — Backend generador

- Crear API FastAPI.
- Crear modelos Pydantic.
- Crear endpoint `/options`.
- Crear endpoint `/generate`.
- Crear endpoint `/download`.
- Implementar generación básica de carpetas.
- Implementar empaquetado zip.

### Fase 3 — Templates base

- Crear template frontend React.
- Crear template backend FastAPI.
- Crear template Docker.
- Crear template README.
- Crear template dev.sh.
- Crear template .env.example.

### Fase 4 — Frontend de configuración

- Crear formulario multi-step.
- Crear selección de stack.
- Crear selección de auth.
- Crear selección de cloud.
- Crear selección de contenedores.
- Conectar con API `/options`.
- Enviar configuración a `/generate`.
- Mostrar link de descarga.

### Fase 5 — Proyecto generado funcional

- Verificar que frontend generado corre.
- Verificar que backend generado corre.
- Verificar que Docker funciona.
- Verificar que dev.sh funciona.
- Verificar que README es coherente.
- Verificar que rutas y login funcionan.

### Fase 6 — CLI npm

- Crear carpeta `cli/`.
- Crear comando interactivo.
- Reutilizar lógica de generación o llamar al backend.
- Probar `npm link`.
- Preparar publicación futura en npm.

### Fase 7 — Validación piloto

- Generar un proyecto real de prueba.
- Medir tiempo usando herramienta.
- Comparar con setup manual.
- Ajustar errores.
- Documentar resultados.

---

## 19. Estructura recomendada del repositorio principal

```txt
reference-architecture-generator/
├── README.md
├── docker-compose.yml
├── .gitignore
├── frontend/
├── backend/
├── templates/
├── generated/
├── cli/
├── docs/
└── examples/
```

---

## 20. Alcance MVP

Para asegurar avance real, el MVP debe enfocarse en:

- Plataforma React.
- Backend FastAPI.
- Generación de proyecto Fullstack React + FastAPI.
- Firebase opcional.
- Docker local.
- dev.sh.
- README generado.
- Descarga zip.

No es necesario para el MVP:

- Publicar realmente en npm.
- Soportar todos los clouds con despliegue completo.
- Soportar Next.js, Node.js, MongoDB, Auth0 desde el inicio.
- Generar Terraform avanzado.
- Tener autenticación en la plataforma generadora.

---

## 21. Alcance versión final deseada

La versión final debería incluir:

- Generación desde web.
- Generación desde CLI npm.
- Soporte React + FastAPI.
- Soporte Firebase Auth.
- Soporte PostgreSQL y Firestore.
- Soporte Docker multi-contenedor.
- Soporte básico para GCP, AWS y Azure.
- Proyecto generado funcional.
- Documentación completa.
- Validación piloto.
- Métricas de reducción de setup.

---

## 22. Métricas de validación del proyecto

La solución debe ser evaluada con los siguientes indicadores:

- Tiempo de setup usando proceso actual.
- Tiempo de setup usando plataforma generadora.
- Porcentaje de tareas reutilizadas.
- Cantidad de archivos generados automáticamente.
- Cantidad de pasos manuales eliminados.
- Tiempo hasta levantar frontend.
- Tiempo hasta levantar backend.
- Tiempo hasta tener login funcional.
- Tiempo hasta tener Docker operativo.

Meta esperada:

- Reducir setup de 4 semanas a menos de 2 semanas.
- Lograr reutilización superior al 70%.
- Reducir retrabajo técnico inicial.
- Generar proyecto base funcional en minutos u horas, no días.

---

## 23. Instrucción para Codex

Implementar la solución siguiendo este documento como guía principal. Priorizar primero el MVP funcional:

1. Backend FastAPI generador.
2. Templates React + FastAPI.
3. Generación zip.
4. Frontend React configurador.
5. Docker y dev.sh.
6. README generado.
7. Validación de proyecto generado.

No implementar funcionalidades avanzadas antes de que el flujo principal funcione de extremo a extremo.

El flujo principal esperado es:

```txt
Usuario configura proyecto en la web → backend genera proyecto → usuario descarga zip → usuario ejecuta dev.sh o docker compose → proyecto base queda funcionando.
```
