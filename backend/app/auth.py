from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated, cast

from fastapi import Depends, HTTPException, status
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy import RedisStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import TenantMembership, User


def _async_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    raise ValueError("Authentication supports PostgreSQL or SQLite database URLs")


def _session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


_session_factory = lru_cache(maxsize=4)(_session_factory)


def _configured_secret() -> str:
    value = get_settings().auth_secret
    secret = value.get_secret_value() if value is not None else ""
    if len(secret) < 32:
        raise HTTPException(
            status_code=503, detail="AUTH_SECRET must contain at least 32 characters"
        )
    return secret


async def get_user_db() -> AsyncGenerator[SQLAlchemyUserDatabase[User, str], None]:
    # The local SQLite mode uses metadata.create_all; production deployments use Alembic.
    from app.services.container import get_container

    get_container()
    session_factory = _session_factory(_async_database_url(get_settings().database_url))
    async with session_factory() as session:
        yield SQLAlchemyUserDatabase(session, User)


class UserManager(BaseUserManager[User, str]):
    def parse_id(self, value: object) -> str:
        return str(value)


async def get_user_manager(
    user_db: Annotated[SQLAlchemyUserDatabase[User, str], Depends(get_user_db)],
) -> AsyncGenerator[UserManager, None]:
    secret = _configured_secret()
    manager = UserManager(user_db)
    manager.reset_password_token_secret = secret
    manager.verification_token_secret = secret
    yield manager


@lru_cache(maxsize=4)
def _redis_client(redis_url: str) -> Redis:
    return cast(Redis, Redis.from_url(redis_url, decode_responses=True))


def _get_strategy() -> RedisStrategy[User, str]:
    settings = get_settings()
    _configured_secret()
    return RedisStrategy(
        redis=_redis_client(settings.redis_url),
        lifetime_seconds=settings.auth_token_lifetime_seconds,
        key_prefix="searchintel:auth-session:",
    )


_cookie = CookieTransport(
    cookie_name="searchintel_session",
    cookie_httponly=True,
    cookie_secure=get_settings().secure_auth_cookies,
    cookie_samesite=get_settings().auth_cookie_samesite,
    cookie_max_age=get_settings().auth_token_lifetime_seconds,
)
auth_backend = AuthenticationBackend(name="session", transport=_cookie, get_strategy=_get_strategy)
fastapi_users = FastAPIUsers[User, str](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
CurrentUser = Annotated[User, Depends(current_active_user)]

_ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}


def require_tenant_role(
    *, user: User, tenant_id: str, minimum_role: str = "viewer", session: Session | None = None
) -> str:
    if minimum_role not in _ROLE_RANK:
        raise ValueError(f"Unknown tenant role: {minimum_role}")
    if session is None:
        from app.services.container import get_container

        with get_container().session_factory() as scoped:
            return _check_membership(
                scoped, user_id=user.id, tenant_id=tenant_id, minimum_role=minimum_role
            )
    return _check_membership(
        session, user_id=user.id, tenant_id=tenant_id, minimum_role=minimum_role
    )


def _check_membership(session: Session, *, user_id: str, tenant_id: str, minimum_role: str) -> str:
    role = session.scalar(
        select(TenantMembership.role).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
    )
    if role is None or _ROLE_RANK.get(role, 0) < _ROLE_RANK[minimum_role]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return role
