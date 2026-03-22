from fastapi import APIRouter
from app.schemas.user import GetOrCreateUserRequest, UserResponse
from app.services.user_service import get_or_create_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/get-or-create", response_model=UserResponse)
def get_or_create_user_endpoint(payload: GetOrCreateUserRequest):
    return get_or_create_user(payload)