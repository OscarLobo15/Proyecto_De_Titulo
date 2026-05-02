from fastapi import APIRouter

from app.database import get_database_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "test-proj2",
        "database": get_database_status(),
    }

