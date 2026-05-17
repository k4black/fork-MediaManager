import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi_users import BaseUserManager, exceptions
from fastapi_users.router import get_oauth_router
from httpx_oauth.oauth2 import OAuth2
from sqlalchemy import select

from media_manager.auth.db import User
from media_manager.auth.schemas import (
    AdminUserCreate,
    AuthMetadata,
    UserCreate,
    UserRead,
)
from media_manager.auth.users import (
    SECRET,
    create_default_admin_user,
    current_superuser,
    fastapi_users,
    get_user_manager,
    openid_client,
    openid_cookie_auth_backend,
)
from media_manager.config import MediaManagerConfig
from media_manager.database import DbSessionDependency


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator:
    await create_default_admin_user()
    yield


users_router = APIRouter(lifespan=lifespan)
auth_metadata_router = APIRouter()


def get_openid_router() -> APIRouter:
    if openid_client:
        return get_oauth_router(
            oauth_client=openid_client,
            backend=openid_cookie_auth_backend,
            get_user_manager=fastapi_users.get_user_manager,
            state_secret=SECRET,
            associate_by_email=True,
            is_verified_by_default=True,
            redirect_url=None,
        )
    # this is there, so that the appropriate routes are created even if OIDC is not configured,
    # e.g. for generating the frontend's openapi client
    return get_oauth_router(
        oauth_client=OAuth2(
            client_id="mock",
            client_secret="mock",  # noqa: S106
            authorize_endpoint="https://example.com/authorize",
            access_token_endpoint="https://example.com/token",  # noqa: S106
        ),
        backend=openid_cookie_auth_backend,
        get_user_manager=fastapi_users.get_user_manager,
        state_secret=SECRET,
        associate_by_email=False,
        is_verified_by_default=False,
        redirect_url=None,
    )


auth_config = MediaManagerConfig().auth
openid_config = auth_config.openid_connect


@users_router.get(
    "/users/all",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(current_superuser)],
)
def get_all_users(db: DbSessionDependency) -> list[UserRead]:
    stmt = select(User)
    result = db.execute(stmt).scalars().unique()
    return [UserRead.model_validate(user) for user in result]


@users_router.post(
    "/users/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(current_superuser)],
)
async def admin_create_user(
    payload: AdminUserCreate,
    user_manager: Annotated[
        BaseUserManager[User, uuid.UUID], Depends(get_user_manager)
    ],
) -> UserRead:
    password = payload.password or user_manager.password_helper.generate()
    try:
        user = await user_manager.create(
            UserCreate(
                email=payload.email,
                password=password,
                is_superuser=payload.is_superuser,
                is_verified=payload.is_verified,
            ),
            safe=False,
        )
    except exceptions.UserAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        ) from exc
    except exceptions.InvalidPasswordException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid password: {exc.reason}",
        ) from exc
    return UserRead.model_validate(user)


@auth_metadata_router.get("/auth/metadata", status_code=status.HTTP_200_OK)
def get_auth_metadata() -> AuthMetadata:
    providers = [openid_config.name] if openid_config.enabled else []
    return AuthMetadata(
        oauth_providers=providers,
        registration_enabled=auth_config.registration_enabled,
    )
