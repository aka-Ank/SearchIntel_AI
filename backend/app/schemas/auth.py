from typing import Literal

from fastapi_users.schemas import BaseUser, BaseUserCreate, BaseUserUpdate
from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseUser[str]):
    pass


class UserCreate(BaseUserCreate):
    pass


class UserUpdate(BaseUserUpdate):
    pass


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantRead(BaseModel):
    id: str
    name: str
    role: str


class TenantMemberCreate(BaseModel):
    email: EmailStr
    role: Literal["viewer", "editor", "admin"] = "viewer"


class TenantMemberRead(BaseModel):
    user_id: str
    email: EmailStr
    role: str
