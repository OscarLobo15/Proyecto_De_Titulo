import base64
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.config import settings
from app.generator import ProjectGenerator
from app.models import GenerateResponse, ProjectConfig
from app.options import OPTIONS

app = FastAPI(title="Reference Architecture Generator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno del servidor: {type(exc).__name__}: {exc}"},
        headers={"Access-Control-Allow-Origin": request.headers.get("origin", "*")},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/options")
def get_options() -> dict:
    return OPTIONS


@app.post("/generate", response_model=GenerateResponse)
def generate_project(config: ProjectConfig) -> GenerateResponse:
    try:
        zip_path = ProjectGenerator(settings.templates_dir, settings.generated_dir).generate(config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Template no encontrado: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = _encode_config(config)
    return GenerateResponse(
        status="success",
        download_url=f"{settings.public_url}/download/{zip_path.name}",
        file_name=zip_path.name,
        config_token=token,
        install_command=f'curl -fsSL "{settings.public_url}/install/{token}" | bash',
        install_command_windows=(
            f'iwr "{settings.public_url}/install/{token}/ps1" | iex'
            if config.target_os in ("windows", "both") else None
        ),
    )


@app.get("/install/{token}", response_class=PlainTextResponse)
def install_script_sh(token: str) -> PlainTextResponse:
    """Returns a bash script the user pipes into bash. Works from any directory."""
    config = _decode_config(token)
    zip_path = _ensure_zip(config)
    download_url = f"{settings.public_url}/download/{zip_path.name}"
    name = config.project_name
    setup = "chmod +x dev.sh setup.sh && ./dev.sh setup" if config.include_dev_script else "echo 'Proyecto listo.'"
    script = f"""#!/usr/bin/env bash
set -e
echo "Creando proyecto {name}..."
TMP=$(mktemp /tmp/{name}.XXXXXX.zip)
curl -fsSL "{download_url}" -o "$TMP"
unzip -qo "$TMP" -d .
rm "$TMP"
cd "{name}"
{setup}
echo ""
echo "Proyecto creado en: $(pwd)"
echo "Para levantar: cd {name} && ./dev.sh start"
"""
    return PlainTextResponse(content=script, media_type="text/x-shellscript")


@app.get("/install/{token}/ps1", response_class=PlainTextResponse)
def install_script_ps1(token: str) -> PlainTextResponse:
    """Returns a PowerShell script the user pipes into iex. Works from any directory."""
    config = _decode_config(token)
    zip_path = _ensure_zip(config)
    download_url = f"{settings.public_url}/download/{zip_path.name}"
    name = config.project_name
    setup = f'.\\dev.ps1 setup' if config.include_dev_script else 'Write-Host "Proyecto listo."'
    script = f"""$ErrorActionPreference = "Stop"
Write-Host "Creando proyecto {name}..."
$tmp = [System.IO.Path]::GetTempFileName() + ".zip"
Invoke-WebRequest "{download_url}" -OutFile $tmp
Expand-Archive $tmp -DestinationPath . -Force
Remove-Item $tmp
Set-Location "{name}"
{setup}
Write-Host ""
Write-Host "Proyecto creado en: $(Get-Location)"
Write-Host "Para levantar: cd {name}; .\\dev.ps1 start"
"""
    return PlainTextResponse(content=script, media_type="text/plain")


@app.get("/download/{file_name}")
def download_project(file_name: str) -> FileResponse:
    if "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="Nombre de archivo invalido.")

    file_path: Path = settings.generated_dir / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    return FileResponse(file_path, filename=file_name, media_type="application/zip")


def _encode_config(config: ProjectConfig) -> str:
    payload = json.dumps(config.model_dump(), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _decode_config(token: str) -> ProjectConfig:
    try:
        padded = token + "=" * ((4 - len(token) % 4) % 4)
        payload = base64.urlsafe_b64decode(padded).decode("utf-8")
        return ProjectConfig(**json.loads(payload))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Token de configuracion invalido.") from exc


def _ensure_zip(config: ProjectConfig) -> Path:
    """Generate a fresh zip so install links never serve stale templates."""
    try:
        return ProjectGenerator(settings.templates_dir, settings.generated_dir).generate(config)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
