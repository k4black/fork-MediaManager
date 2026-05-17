import uuid

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str | None = None
    is_superuser: bool = False
    is_verified: bool = True


class AuthMetadata(BaseModel):
    oauth_providers: list[str]
    registration_enabled: bool
