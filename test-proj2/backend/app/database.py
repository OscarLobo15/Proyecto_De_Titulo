from app.config import settings


def get_database_status() -> dict[str, str]:
    if not settings.database_url:
        return {"configured": "false", "provider": "postgresql"}

    return {"configured": "true", "provider": "postgresql"}

