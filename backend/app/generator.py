import shutil
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.models import ProjectConfig


class ProjectGenerator:
    def __init__(self, templates_dir: Path, generated_dir: Path) -> None:
        self.templates_dir = templates_dir
        self.generated_dir = generated_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )

    def generate(self, config: ProjectConfig) -> Path:
        if not self.templates_dir.exists():
            raise FileNotFoundError(self.templates_dir)

        self.generated_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        build_dir = self.generated_dir / f"{config.project_name}-{timestamp}"
        zip_path = self.generated_dir / f"{config.project_name}.zip"

        if build_dir.exists():
            shutil.rmtree(build_dir)
        if zip_path.exists():
            zip_path.unlink()

        build_dir.mkdir(parents=True)
        context = self._build_context(config)

        for template_group in self._selected_template_groups(config):
            if template_group == "services":
                self._render_service_templates(build_dir, context)
            else:
                self._render_template_group(template_group, build_dir, context)

        if config.include_dev_script:
            dev_script = build_dir / "dev.sh"
            if dev_script.exists():
                dev_script.chmod(0o755)
            setup_script = build_dir / "setup.sh"
            if setup_script.exists():
                setup_script.chmod(0o755)
            root_deploy_script = build_dir / "deploy.py"
            if root_deploy_script.exists():
                root_deploy_script.chmod(0o755)
            deploy_script = build_dir / "deploy" / "gcp" / "deploy.sh"
            if deploy_script.exists():
                deploy_script.chmod(0o755)
            aws_deploy_script = build_dir / "deploy" / "aws" / "deploy.sh"
            if aws_deploy_script.exists():
                aws_deploy_script.chmod(0o755)
            azure_deploy_script = build_dir / "deploy" / "azure" / "deploy.sh"
            if azure_deploy_script.exists():
                azure_deploy_script.chmod(0o755)

        self._validate_generated_project(build_dir, context)
        self._zip_directory(build_dir, zip_path, config.project_name)
        shutil.rmtree(build_dir)
        return zip_path

    def _selected_template_groups(self, config: ProjectConfig) -> list[str]:
        groups = ["base"]

        if config.project_type in ["web", "fullstack"]:
            groups.append("frontend-react")

        if config.project_type in ["api", "fullstack"]:
            groups.append("backend-fastapi")

        if config.auth == "firebase" and config.project_type in ["web", "fullstack"]:
            groups.append("auth-firebase")
        if config.include_docker:
            groups.append("docker")
        if config.project_type in ["api", "fullstack"] and (
            config.include_services or "services" in config.containers or config.project_profile == "microservices"
        ):
            groups.append("services")
        if config.cloud != "local":
            groups.append(f"cloud-{config.cloud}")

        return groups

    def _render_service_templates(self, destination: Path, context: dict) -> None:
        service_count = context["service_count"]
        if service_count <= 0:
            return

        source = self.templates_dir / "services"
        if not source.exists():
            raise FileNotFoundError(source)

        self._render_template_group("services", destination, context)

        template_dir = destination / "services" / "template"
        if not template_dir.exists():
            return

        for service in context["extra_services"]:
            service_dir = destination / "services" / service["slug"]
            if service_dir.exists():
                shutil.rmtree(service_dir)
            shutil.copytree(template_dir, service_dir)

        shutil.rmtree(template_dir)

    def _render_template_group(self, group: str, destination: Path, context: dict) -> None:
        source = self.templates_dir / group
        if not source.exists():
            raise FileNotFoundError(source)

        for item in source.rglob("*"):
            if item.is_dir():
                continue

            relative_path = item.relative_to(source)
            target_relative = Path(str(relative_path).removesuffix(".j2"))
            if self._should_skip_path(target_relative, context):
                continue
            target = destination / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)

            if item.suffix == ".j2":
                template_name = str(Path(group) / relative_path)
                rendered = self.env.get_template(template_name).render(**context)
                target.write_text(rendered, encoding="utf-8")
            else:
                shutil.copy2(item, target)

    def _should_skip_path(self, relative_path: Path, context: dict) -> bool:
        parts = relative_path.parts
        if not parts:
            return False

        if parts[0] == "frontend" and not context["has_frontend"]:
            return True
        if parts[0] == "backend" and not context["has_backend"]:
            return True
        if parts[0] == "services" and not (context["has_backend"] and context["include_services"]):
            return True
        if relative_path.name == "Login.jsx" and not context["include_login"]:
            return True
        if relative_path.name == "ProtectedRoute.jsx" and not context["include_login"]:
            return True
        if relative_path.name == "Home.jsx":
            return True
        if "context" in parts and not context["include_login"]:
            return True
        if relative_path.name in ["authService.js", "firebase.js", "firebaseNotes.md"] and not context["include_login"]:
            return True
        if relative_path.name == "Agent.jsx" and not context["include_ai"]:
            return True
        if relative_path.name == "dev.sh" and context["target_os"] == "windows":
            return True
        if relative_path.name == "dev.ps1" and context["target_os"] == "mac":
            return True
        if relative_path.name == "setup.sh" and context["target_os"] == "windows":
            return True
        # target_os == "both": skip nothing, include both .sh and .ps1
        if relative_path.name in ["dev.sh", "dev.ps1", "setup.sh"] and not context["include_dev_script"]:
            return True

        return False

    def _validate_generated_project(self, project_dir: Path, context: dict) -> None:
        if context["has_frontend"]:
            self._validate_frontend_imports(project_dir / "frontend" / "src")

    def _validate_frontend_imports(self, src_dir: Path) -> None:
        if not src_dir.exists():
            raise ValueError("El frontend generado no contiene frontend/src.")

        import_pattern = re.compile(r"(?:import\s+(?:[\s\S]*?\s+from\s+)?|export\s+[\s\S]*?\s+from\s+)['\"](\.{1,2}/[^'\"]+)['\"]")

        for source_file in src_dir.rglob("*"):
            if source_file.suffix not in {".js", ".jsx"}:
                continue

            content = source_file.read_text(encoding="utf-8")
            for match in import_pattern.finditer(content):
                import_path = match.group(1)
                if not self._resolve_frontend_import(source_file.parent, import_path):
                    relative_source = source_file.relative_to(src_dir.parent)
                    raise ValueError(
                        f"Import relativo invalido en {relative_source}: {import_path}"
                    )

    def _resolve_frontend_import(self, base_dir: Path, import_path: str) -> bool:
        candidate = (base_dir / import_path).resolve()
        allowed_suffixes = ["", ".js", ".jsx", ".json", ".css"]

        for suffix in allowed_suffixes:
            file_candidate = candidate if not suffix else candidate.with_suffix(suffix)
            if file_candidate.is_file():
                return True

        if candidate.is_dir():
            return any((candidate / f"index{suffix}").is_file() for suffix in [".js", ".jsx"])

        return False

    def _zip_directory(self, source: Path, zip_path: Path, archive_root: str) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in source.rglob("*"):
                if file_path.is_file():
                    archive_name = Path(archive_root) / file_path.relative_to(source)
                    zip_file.write(file_path, archive_name)

    def _build_context(self, config: ProjectConfig) -> dict:
        has_frontend = config.project_type in ["web", "fullstack"]
        has_backend = config.project_type in ["api", "fullstack"]
        uses_database = has_backend and config.database != "none"
        uses_postgres = has_backend and config.database == "postgresql"
        uses_firestore = has_backend and config.database == "firestore"
        uses_supabase = config.auth == "supabase" or config.database == "supabase"
        uses_firebase = has_frontend and config.auth == "firebase"
        include_ai = config.project_profile == "ai"
        include_ai_ui = include_ai and has_frontend
        include_ai_backend = include_ai and has_backend
        include_login = has_frontend and config.auth != "none"
        service_count = config.service_count if has_backend and config.include_services else 0
        frontend_port = 5174
        backend_port = 8001
        modules = self._build_modules(config)
        extra_services = [
            {
                "name": self._service_name_for_index(config, index),
                "slug": self._service_slug_for_index(config, index),
                "port": backend_port + index,
            }
            for index in range(1, service_count + 1)
        ]
        deploy_targets = []
        if has_frontend:
            deploy_targets.append(
                {
                    "key": "frontend",
                    "label": "Frontend",
                    "service_name": f"{config.project_name}-frontend",
                    "image_name": f"{config.project_name}-frontend",
                    "port": frontend_port,
                    "context": "frontend",
                    "dockerfile": "frontend/Dockerfile",
                    "public": True,
                    "memory": "512Mi",
                    "cpu": "1",
                    "env": {"VITE_API_URL": ""},
                }
            )
        if has_backend:
            deploy_targets.append(
                {
                    "key": "backend",
                    "label": "Backend",
                    "service_name": f"{config.project_name}-backend",
                    "image_name": f"{config.project_name}-backend",
                    "port": backend_port,
                    "context": "backend",
                    "dockerfile": "backend/Dockerfile",
                    "public": True,
                    "memory": "1Gi",
                    "cpu": "1",
                    "env": {"APP_ENV": "production", "API_PORT": str(backend_port)},
                }
            )
        for service in extra_services:
            deploy_targets.append(
                {
                    "key": service["slug"],
                    "label": service["name"],
                    "service_name": f"{config.project_name}-{service['slug']}",
                    "image_name": f"{config.project_name}-{service['slug']}",
                    "port": service["port"],
                    "context": f"services/{service['slug']}",
                    "dockerfile": f"services/{service['slug']}/Dockerfile",
                    "public": False,
                    "memory": "1Gi",
                    "cpu": "1",
                    "env": {"ENVIRONMENT": "production", "PORT": str(service["port"])},
                }
            )

        return {
            "project": config,
            "project_name": config.project_name,
            "project_title": config.project_name.replace("-", " ").title(),
            "description": config.description,
            "frontend_port": frontend_port,
            "backend_port": backend_port,
            "database_port": 5432,
            "has_frontend": has_frontend,
            "has_backend": has_backend,
            "uses_database": uses_database,
            "uses_postgres": uses_postgres,
            "uses_firestore": uses_firestore,
            "uses_supabase": uses_supabase,
            "uses_firebase": uses_firebase,
            "include_login": include_login,
            "include_ai": include_ai,
            "include_ai_ui": include_ai_ui,
            "include_ai_backend": include_ai_backend,
            "include_docker": config.include_docker,
            "include_dev_script": config.include_dev_script,
            "include_langgraph": config.include_langgraph or include_ai_backend,
            "target_os": config.target_os,
            "dev_command": ".\\dev.ps1 start" if config.target_os == "windows" else "./dev.sh start",
            "setup_command": ".\\dev.ps1 setup" if config.target_os == "windows" else "./dev.sh setup",
            "containers": config.containers,
            "cloud": config.cloud,
            "cloud_label": self._cloud_label(config.cloud),
            "project_profile": config.project_profile,
            "include_services": config.include_services and service_count > 0,
            "service_count": service_count,
            "modules": modules,
            "role_labels": self._build_role_labels(config),
            "navigation_layout": config.navigation_layout,
            "login_variant": config.login_variant,
            "experience_mode": config.experience_mode,
            "admin_style": config.admin_style,
            "navigation_sections": self._build_navigation_sections(config),
            "pages": config.pages,
            "primary_route": self._compute_primary_route(config),
            "extra_services": extra_services,
            "deploy_targets": deploy_targets,
        }

    @staticmethod
    def _slugify(text: str) -> str:
        normalized = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "-", normalized.strip().lower()).strip("-")

    def _cloud_label(self, cloud: str) -> str:
        return {
            "local": "Local Docker",
            "gcp": "GCP Cloud Run",
            "aws": "AWS App Runner / ECS",
            "azure": "Azure Container Apps",
        }[cloud]

    def _build_modules(self, config: ProjectConfig) -> list[dict[str, str]]:
        source_modules = config.functional_modules or ["operaciones", "usuarios", "reportes"]
        modules = []
        for module in source_modules:
            label = module.strip().replace("-", " ").title()
            slug = self._slugify(module)
            if slug and slug not in [item["slug"] for item in modules]:
                modules.append({"slug": slug, "label": label})
        return modules[:12] or [{"slug": "operaciones", "label": "Operaciones"}]

    def _build_role_labels(self, config: ProjectConfig) -> list[str]:
        source_roles = config.user_roles or ["admin"]
        roles = []
        for role in source_roles:
            slug = self._slugify(role)
            if slug and slug not in roles:
                roles.append(slug)
        return roles[:8]

    def _build_navigation_sections(self, config: ProjectConfig) -> list[dict[str, str]]:
        sections = []
        for section in config.navigation_sections or []:
            slug = self._slugify(section)
            label = section.strip().replace("-", " ").title()
            if slug and slug not in [item["slug"] for item in sections]:
                sections.append({"slug": slug, "label": label})
        return sections[:12]

    def _compute_primary_route(self, config: ProjectConfig) -> str:
        pages = config.pages or ["workspace"]
        for page in ["workspace", "dashboard"]:
            if page in pages:
                return f"/app/{page}"
        for page in pages:
            if page not in ("login", "not-found"):
                return f"/app/{page}"
        return "/app/workspace"

    def _service_name_for_index(self, config: ProjectConfig, index: int) -> str:
        modules = self._build_modules(config)
        if config.project_profile == "ai" and index == 1:
            return "Agent Service"
        if index - 1 < len(modules):
            return f"{modules[index - 1]['label']} Service"
        return f"Service {index}"

    def _service_slug_for_index(self, config: ProjectConfig, index: int) -> str:
        name = self._service_name_for_index(config, index)
        slug = self._slugify(name)
        return slug or f"service-{index}"
