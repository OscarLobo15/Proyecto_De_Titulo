import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


FrontendOption = Literal["react"]
BackendOption = Literal["fastapi"]
AuthOption = Literal["firebase", "supabase", "none"]
DatabaseOption = Literal["postgresql", "firestore", "supabase", "none"]
CloudOption = Literal["gcp", "aws", "azure", "local"]
ProjectType = Literal["web", "api", "fullstack"]
ProjectProfile = Literal["standard", "ai", "microservices", "api-only"]
ContainerOption = Literal["frontend", "backend", "services"]
TargetOS = Literal["mac", "windows", "both"]
NavigationLayout = Literal["sidebar", "navbar"]
LoginVariant = Literal["ibm-classic", "digital-workers", "digital-buyers"]
ExperienceMode = Literal["admin", "user"]
AdminStyle = Literal["operations", "business"]


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
    containers: list[ContainerOption] = Field(default_factory=lambda: ["frontend", "backend"])
    include_docker: bool = True
    include_dev_script: bool = True
    include_services: bool = False
    include_langgraph: bool = False
    service_count: int = Field(default=0, ge=0, le=5)
    target_os: TargetOS = "mac"
    navigation_layout: NavigationLayout = "sidebar"
    login_variant: LoginVariant = "ibm-classic"
    experience_mode: ExperienceMode = "admin"
    admin_style: AdminStyle = "operations"
    pages: list[str] = Field(default_factory=lambda: ["login", "workspace", "settings", "not-found"])
    navigation_sections: list[str] = Field(default_factory=list)
    functional_modules: list[str] = Field(default_factory=lambda: ["operaciones", "usuarios", "reportes"])
    user_roles: list[str] = Field(default_factory=list)

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

    @field_validator("functional_modules", "user_roles", "navigation_sections")
    @classmethod
    def validate_named_items(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            normalized = item.strip().lower()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned[:8]

    @model_validator(mode="after")
    def normalize_by_project_type(self) -> "ProjectConfig":
        if self.project_type == "web":
            self.database = "none"
            self.containers = [item for item in self.containers if item == "frontend"]
            if "frontend" not in self.containers:
                self.containers = ["frontend"]
            self.include_services = False
            self.service_count = 0
            self.include_langgraph = False

        if self.project_type == "api":
            self.containers = [item for item in self.containers if item in ["backend", "services"]]
            if "backend" not in self.containers:
                self.containers.insert(0, "backend")
            self.pages = []
            self.navigation_sections = []

        if self.project_type == "fullstack":
            if "frontend" not in self.containers:
                self.containers.insert(0, "frontend")
            if "backend" not in self.containers:
                self.containers.append("backend")

        if self.project_profile == "ai" and self.project_type != "web":
            self.include_langgraph = True

        if self.project_profile == "microservices" and self.project_type != "web":
            self.include_services = True
            self.service_count = max(self.service_count, 2)
            if "services" not in self.containers:
                self.containers.append("services")
        elif self.service_count > 0 and self.project_type != "web":
            self.include_services = True
            if "services" not in self.containers:
                self.containers.append("services")
        else:
            self.include_services = False
            self.service_count = 0

        if self.auth == "none":
            self.pages = [page for page in self.pages if page != "login"]
        elif self.project_type != "api" and "login" not in self.pages:
            self.pages.append("login")

        return self


class GenerateResponse(BaseModel):
    status: Literal["success"]
    download_url: str
    file_name: str
    config_token: str
    install_command: str
    install_command_windows: Optional[str] = None


class AnalyzeProjectRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El mensaje no puede estar vacio.")
        return cleaned


class ProjectAnalysis(BaseModel):
    project_type: str = ""
    frontend: str = ""
    backend: str = ""
    database: str = ""
    auth: str = ""
    deployment: str = ""
    required_modules: list[str] = Field(default_factory=list)
    recommended_templates: list[str] = Field(default_factory=list)
    notes: str = ""


class AnalyzeProjectResponse(BaseModel):
    success: Literal[True]
    analysis: ProjectAnalysis


class AIGenerateProjectRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    project_name: str = Field(min_length=3, max_length=60)

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El prompt no puede estar vacio.")
        return cleaned

    @field_validator("project_name")
    @classmethod
    def validate_ai_project_name(cls, value: str) -> str:
        return ProjectConfig.validate_project_name(value)


class AIGenerateProjectResponse(BaseModel):
    success: Literal[True]
    project_name: str
    selected_architecture: dict
    selected_templates: list[str]
    project_config: dict
    download_url: str
    file_name: str
    install_command: str
    install_command_windows: Optional[str] = None
    message: str
