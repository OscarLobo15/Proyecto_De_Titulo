from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    generator_env: str = "development"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    generated_projects_dir: str = "generated"
    public_url: str = "http://127.0.0.1:8000"  # Override in prod: PUBLIC_URL=https://your-domain.com
    ai_server_url: Optional[str] = None
    ai_generate_endpoint: str = "/generate"
    ai_timeout_seconds: float = 300
    ai_project_generation_timeout_seconds: float = 300
    ai_request_retries: int = 2
    ai_request_retry_delay_seconds: float = 2

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

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
