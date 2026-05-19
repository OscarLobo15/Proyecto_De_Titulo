import base64
import json
import logging
from pathlib import Path

import io

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.ai.project_analysis_graph import AIModelParseError, analyze_project_with_ai
from app.ai.project_generation_graph import AIGenerationError, TemplateSelectionError, generate_project_with_ai
from app.ai.project_planning_graph import plan_project_with_ai
from app.config import settings
from app.generator import ProjectGenerator
from app.models import (
    AIGenerateProjectRequest,
    AIGenerateProjectResponse,
    AnalyzeProjectRequest,
    AnalyzeProjectResponse,
    GenerateResponse,
    PlanProjectRequest,
    PlanProjectResponse,
    ProjectConfig,
)
from app.options import OPTIONS
from app.services.ai_client import AIConfigurationError, AIRemoteServiceError

try:
    import fitz
except ImportError:  # pragma: no cover - optional runtime dependency
    fitz = None

try:
    import pdfplumber
except ImportError:  # pragma: no cover - optional fallback dependency
    pdfplumber = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="Reference Architecture Generator API", version="1.0.0")

MAX_PDF_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES_TO_EXTRACT = 80
MAX_PDF_TEXT_CHARS = 200000

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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    if request.url.path in {"/api/ai/analyze-project", "/api/ai/generate-project"}:
        return JSONResponse(
            status_code=400,
            content={"detail": "El request IA debe incluir campos validos y no vacios."},
            headers={"Access-Control-Allow-Origin": request.headers.get("origin", "*")},
        )
    return await request_validation_exception_handler(request, exc)


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


@app.post("/api/ai/analyze-project", response_model=AnalyzeProjectResponse)
def analyze_project(request: AnalyzeProjectRequest) -> AnalyzeProjectResponse:
    try:
        analysis = analyze_project_with_ai(request.message)
    except AIConfigurationError as exc:
        logger.warning("AI configuration error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIRemoteServiceError as exc:
        logger.warning("AI remote service error: %s", exc)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except AIModelParseError as exc:
        logger.warning("AI model parse error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AnalyzeProjectResponse(success=True, analysis=analysis)


@app.post("/api/ai/generate-project", response_model=AIGenerateProjectResponse)
def ai_generate_project(request: AIGenerateProjectRequest) -> AIGenerateProjectResponse:
    try:
        result = generate_project_with_ai(request.prompt, request.project_name)
    except AIConfigurationError as exc:
        logger.warning("AI configuration error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIRemoteServiceError as exc:
        logger.warning("AI remote service error: %s", exc)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except TemplateSelectionError as exc:
        logger.warning("AI template selection error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except AIGenerationError as exc:
        logger.warning("AI project generation error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    config = result["project_config"]
    return AIGenerateProjectResponse(
        success=True,
        project_name=config.project_name,
        selected_architecture=result["selected_architecture"],
        selected_templates=result["selected_templates"],
        project_config=config.model_dump(),
        download_url=result["download_url"],
        file_name=result["file_name"],
        install_command=result["install_command"],
        install_command_windows=result.get("install_command_windows"),
        message=result["message"],
    )


@app.post("/api/ai/plan-project", response_model=PlanProjectResponse)
def plan_project(request: PlanProjectRequest) -> PlanProjectResponse:
    try:
        resolved_name, plan = plan_project_with_ai(
            description=request.description,
            project_name=request.project_name,
            selected_architecture=request.selected_architecture,
        )
    except AIConfigurationError as exc:
        logger.warning("AI configuration error in plan-project: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIRemoteServiceError as exc:
        logger.warning("AI remote service error in plan-project: %s", exc)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in plan-project: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error generando el plan IBM: {exc}") from exc

    return PlanProjectResponse(success=True, project_name=resolved_name, plan=plan)


@app.post("/api/ai/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    is_pdf = file.content_type == "application/pdf" or (file.filename or "").lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF.")
    contents = await file.read()
    if len(contents) > MAX_PDF_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El PDF supera el maximo permitido de 15 MB.")

    try:
        extraction = _extract_pdf_text(contents)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"No fue posible extraer texto del PDF: {exc}") from exc

    text = extraction["text"]
    if not text.strip():
        raise HTTPException(status_code=422, detail="El PDF no contiene texto extraíble. Asegúrese de que el archivo no sea una imagen escaneada.")
    return {
        "text": text.strip(),
        "file_name": file.filename,
        "page_count": extraction["page_count"],
        "extracted_pages": extraction["extracted_pages"],
        "character_count": len(text.strip()),
        "truncated": extraction["truncated"],
        "extractor": extraction["extractor"],
    }


def _extract_pdf_text(contents: bytes) -> dict:
    if fitz is not None:
        return _extract_pdf_text_with_pymupdf(contents)

    if pdfplumber is not None:
        return _extract_pdf_text_with_pdfplumber(contents)

    raise RuntimeError("No hay extractor PDF disponible. Instale PyMuPDF o pdfplumber.")


def _append_pdf_text_chunk(chunks: list[str], page_text: str, total_chars: int) -> tuple[int, bool]:
    remaining_chars = MAX_PDF_TEXT_CHARS - total_chars
    if remaining_chars <= 0:
        return total_chars, True

    if len(page_text) > remaining_chars:
        chunks.append(page_text[:remaining_chars])
        return total_chars + remaining_chars, True

    chunks.append(page_text)
    return total_chars + len(page_text), False


def _extract_pdf_text_with_pymupdf(contents: bytes) -> dict:
    document = fitz.open(stream=contents, filetype="pdf")
    try:
        page_count = document.page_count
        extracted_pages = min(page_count, MAX_PDF_PAGES_TO_EXTRACT)
        chunks: list[str] = []
        total_chars = 0
        truncated = page_count > MAX_PDF_PAGES_TO_EXTRACT

        for page_index in range(extracted_pages):
            page_text = document.load_page(page_index).get_text("text") or ""
            if not page_text:
                continue

            total_chars, reached_limit = _append_pdf_text_chunk(chunks, page_text, total_chars)
            if reached_limit:
                truncated = True
                break

        return {
            "text": "\n".join(chunks),
            "page_count": page_count,
            "extracted_pages": extracted_pages,
            "truncated": truncated,
            "extractor": "pymupdf",
        }
    finally:
        document.close()


def _extract_pdf_text_with_pdfplumber(contents: bytes) -> dict:
    with pdfplumber.open(io.BytesIO(contents)) as pdf:
        page_count = len(pdf.pages)
        extracted_pages = min(page_count, MAX_PDF_PAGES_TO_EXTRACT)
        chunks: list[str] = []
        total_chars = 0
        truncated = page_count > MAX_PDF_PAGES_TO_EXTRACT

        for page in pdf.pages[:extracted_pages]:
            page_text = page.extract_text() or ""
            if not page_text:
                continue

            total_chars, reached_limit = _append_pdf_text_chunk(chunks, page_text, total_chars)
            if reached_limit:
                truncated = True
                break

        return {
            "text": "\n".join(chunks),
            "page_count": page_count,
            "extracted_pages": extracted_pages,
            "truncated": truncated,
            "extractor": "pdfplumber",
        }


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
