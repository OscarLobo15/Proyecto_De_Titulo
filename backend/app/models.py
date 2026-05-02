import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


FrontendOption = Literal["react"]
BackendOption = Literal["fastapi"]
AuthOption = Literal["firebase", "none"]
DatabaseOption = Literal["postgresql", "firestore", "none"]
CloudOption = Literal["gcp", "aws", "azure", "local"]
ProjectType = Literal["web", "api", "fullstack"]
ProjectProfile = Literal["standard", "ai", "microservices", "api-only"]
ContainerOption = Literal["frontend", "backend", "database", "services"]
TargetOS = Literal["mac", "windows", "both"]


class ProjectConfig(BaseModel):
    project_name: str = Field(min_length=3, max_length=60)
    description: str = Field(default="Proyecto generado desde arquitectura base.", max_length=180)
    project_type: ProjectType = "fullstack"
    project_profile: ProjectProfile = "standard"
    frontend: FrontendOption = "react"
    backend: BackendOption = "fastapi"
    auth: AuthOption = "firebase"
    database: DatabaseOption = "postgresql"
    cloud: CloudOption = "local"
    containers: list[ContainerOption] = Field(default_factory=lambda: ["frontend", "backend", "database"])
    include_docker: bool = True
    include_dev_script: bool = True
    include_services: bool = False
    include_langgraph: bool = False
    target_os: TargetOS = "mac"
    pages: list[str] = Field(default_factory=lambda: ["home", "login", "dashboard", "settings", "not-found"])

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,58}[a-z0-9]", normalized):
            raise ValueError("El nombre debe usar letras, numeros o guiones, sin guion al inicio o final.")
        return normalized

    @field_validator("containers")
    @classmethod
    def validate_containers(cls, value: list[ContainerOption]) -> list[ContainerOption]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def normalize_by_project_type(self) -> "ProjectConfig":
        if self.project_type == "web":
            self.database = "none"
            self.containers = [item for item in self.containers if item == "frontend"]
            if "frontend" not in self.containers:
                self.containers = ["frontend"]
            self.include_services = False

        if self.project_type == "api":
            self.auth = "none"
            self.containers = [item for item in self.containers if item in ["backend", "database", "services"]]
            if "backend" not in self.containers:
                self.containers.insert(0, "backend")

        return self


class GenerateResponse(BaseModel):
    status: Literal["success"]
    download_url: str
    file_name: str
    config_token: str
    install_command: str
    install_command_windows: str | None = None
