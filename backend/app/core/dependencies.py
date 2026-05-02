from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt as jose_jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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


async def _verify_oauth2_bearer(token: str, db: AsyncSession) -> tuple[uuid.UUID, str]:
    """Validate an OAuth2 Client Credentials Bearer token. Returns (tenant_id, 'api_key')."""
    try:
        payload = jose_jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OAuth2 token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "oauth2_client":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OAuth2 token payload")
    return uuid.UUID(tenant_id_str), "api_key"


async def _verify_mtls(fingerprint: str, db: AsyncSession) -> tuple[uuid.UUID, str]:
    """Validate an mTLS client certificate fingerprint. Returns (tenant_id, 'api_key')."""
    from app.models.mtls_certificate import MTLSCertificate

    cert = (await db.execute(
        select(MTLSCertificate).where(
            MTLSCertificate.fingerprint_sha256 == fingerprint,
            MTLSCertificate.is_active.is_(True),
        )
    )).scalar_one_or_none()

    if cert is None or cert.valid_until < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired mTLS certificate",
        )

    await db.execute(
        update(MTLSCertificate)
        .where(MTLSCertificate.id == cert.id)
        .values(last_used_at=datetime.utcnow())
    )
    await db.commit()
    return cert.tenant_id, "api_key"


async def get_execute_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> tuple[uuid.UUID, str]:
    """Return (tenant_id, triggered_by) from X-API-Key, Bearer JWT, OAuth2 Bearer or mTLS.

    Checked in order: X-API-Key → X-Client-Cert-Fingerprint (mTLS) → Bearer JWT → 401.
    For Bearer, detects token type: 'access' (user session) or 'oauth2_client'.
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

    fingerprint = request.headers.get("X-Client-Cert-Fingerprint")
    if fingerprint:
        return await _verify_mtls(fingerprint, db)

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_type = payload.get("type")

        if token_type == "access":
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
            user = result.scalar_one_or_none()
            if user is None or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                )
            return user.tenant_id, "dashboard"

        if token_type == "oauth2_client":
            return await _verify_oauth2_bearer(token, db)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (X-API-Key, Bearer token or mTLS)",
    )
