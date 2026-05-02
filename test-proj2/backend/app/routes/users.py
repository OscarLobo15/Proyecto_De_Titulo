from fastapi import APIRouter

from app.schemas.user_schema import UserResponse
from app.services.user_service import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def me() -> UserResponse:
    return get_current_user()

