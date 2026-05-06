import shutil
import zipfile
from datetime import datetime
from pathlib import Path

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
        extra_services = [
            {"name": f"Service {index}", "slug": f"service-{index}", "port": 8001 + index}
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
                    "port": 5173,
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
                    "port": 8000,
                    "context": "backend",
                    "dockerfile": "backend/Dockerfile",
                    "public": True,
                    "memory": "1Gi",
                    "cpu": "1",
                    "env": {"APP_ENV": "production", "API_PORT": "8000"},
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
            "frontend_port": 5173,
            "backend_port": 8000,
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
            "extra_services": extra_services,
            "deploy_targets": deploy_targets,
        }

    def _cloud_label(self, cloud: str) -> str:
        return {
            "local": "Local Docker",
            "gcp": "GCP Cloud Run",
            "aws": "AWS App Runner / ECS",
            "azure": "Azure Container Apps",
        }[cloud]
