from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    generator_env: str = "development"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    generated_projects_dir: str = "generated"
    public_url: str = "http://127.0.0.1:8000"  # Override in prod: PUBLIC_URL=https://your-domain.com

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def templates_dir(self) -> Path:
        mounted_templates = self.project_root / "templates"
        if mounted_templates.exists():
            return mounted_templates
        return self.project_root.parent / "templates"

    @property
    def generated_dir(self) -> Path:
        return self.project_root / self.generated_projects_dir


settings = Settings()
