from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_LEVEL
from app.core.redis import get_redis
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.user import User

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Missing subject")
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def _role_guard(min_role: str):
    """Return a FastAPI dependency that requires the current user to have at least min_role."""
    min_level = ROLE_LEVEL[min_role]

    async def guard(current_user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVEL.get(current_user.role, 0) < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {min_role}",
            )
        return current_user

    return guard


require_super_admin = _role_guard("super_admin")
require_admin_or_above = _role_guard("admin")
require_developer_or_above = _role_guard("developer")


async def get_execute_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> tuple[uuid.UUID, str]:
    """Return (tenant_id, triggered_by) from X-API-Key header or Bearer token.

    Checked in this order: X-API-Key → Bearer JWT → 401.
    Raises 429 when the API key's hourly rate limit is exceeded.
    """
    from app.services import api_key_service  # local import — avoids circular dependency

    raw_key = request.headers.get("X-API-Key")
    if raw_key:
        api_key = await api_key_service.validate_api_key(raw_key, db)
        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
            )
        if not await api_key_service.check_rate_limit(api_key, redis):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        return api_key.tenant_id, "api_key"

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise ValueError
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        return user.tenant_id, "dashboard"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (Bearer token or X-API-Key)",
    )
