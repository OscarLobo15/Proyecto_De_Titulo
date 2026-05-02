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
            self._render_template_group(template_group, build_dir, context)

        if config.include_dev_script:
            dev_script = build_dir / "dev.sh"
            if dev_script.exists():
                dev_script.chmod(0o755)
            setup_script = build_dir / "setup.sh"
            if setup_script.exists():
                setup_script.chmod(0o755)

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
        uses_firebase = has_frontend and config.auth == "firebase"

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
            "uses_firebase": uses_firebase,
            "include_docker": config.include_docker,
            "include_dev_script": config.include_dev_script,
            "include_langgraph": config.include_langgraph,
            "target_os": config.target_os,
            "dev_command": ".\\dev.ps1 start" if config.target_os == "windows" else "./dev.sh start",
            "setup_command": ".\\dev.ps1 setup" if config.target_os == "windows" else "./dev.sh setup",
            "containers": config.containers,
            "cloud": config.cloud,
            "cloud_label": self._cloud_label(config.cloud),
            "project_profile": config.project_profile,
            "include_services": config.include_services,
        }

    def _cloud_label(self, cloud: str) -> str:
        return {
            "local": "Local Docker",
            "gcp": "GCP Cloud Run",
            "aws": "AWS App Runner / ECS",
            "azure": "Azure Container Apps",
        }[cloud]
