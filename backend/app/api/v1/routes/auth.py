from fastapi import APIRouter

from app.auth import CurrentUser, auth_backend, fastapi_users
from app.models.auth import User
from app.schemas.auth import UserCreate, UserRead, UserUpdate

router = APIRouter()
router.include_router(fastapi_users.get_auth_router(auth_backend))
router.include_router(fastapi_users.get_register_router(UserRead, UserCreate))
router.include_router(fastapi_users.get_users_router(UserRead, UserUpdate))


@router.get("/me", response_model=UserRead)
def read_current_user(user: CurrentUser) -> User:
    return user
