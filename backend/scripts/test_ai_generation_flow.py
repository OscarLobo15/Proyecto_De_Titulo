import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai.project_generation_graph import generate_project_with_ai
from app.services.ai_client import RemoteLLMClient


class FakeLLMClient:
    def generate(self, prompt: str) -> str:
        return json.dumps(
            {
                "project_type": "fullstack",
                "functional_modules": ["reservas", "calendario", "dashboard"],
                "user_roles": ["paciente", "psicologo", "administrador"],
                "needs_auth": True,
                "needs_database": True,
                "needs_deployment": True,
                "needs_docker": True,
                "cloud_target": "gcp",
                "future_integrations": ["upload-pdf-pcr"],
                "technical_constraints": ["postgresql", "docker"],
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test for the AI project generation graph.")
    parser.add_argument("--remote", action="store_true", help="Use the configured remote LLM instead of the fake client.")
    args = parser.parse_args()

    client = RemoteLLMClient() if args.remote else FakeLLMClient()
    result = generate_project_with_ai(
        prompt=(
            "Necesito una plataforma web para gestion de reservas psicologicas. "
            "Debe tener pacientes, psicologos, administrador, autenticacion, calendario, "
            "dashboard, PostgreSQL, Docker y despliegue cloud."
        ),
        project_name="qa-ai-reservas",
        llm_client=client,
    )

    zip_path = result["zip_path"]
    required_entries = [
        "qa-ai-reservas/README.md",
        "qa-ai-reservas/frontend/package.json",
        "qa-ai-reservas/backend/requirements.txt",
        "qa-ai-reservas/docker-compose.yml",
        "qa-ai-reservas/.env.example",
        "qa-ai-reservas/dev.sh",
    ]
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        missing = [entry for entry in required_entries if entry not in names]

    if missing:
        raise SystemExit(f"ZIP incompleto. Faltan: {missing}")

    print(
        json.dumps(
            {
                "ok": True,
                "zip": str(zip_path),
                "selected_templates": result["selected_templates"],
                "download_url": result["download_url"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
