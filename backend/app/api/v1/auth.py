import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.user import RefreshRequest, Token, UserCreate, UserLogin, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_PREFIX = "refresh:"


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Token:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    tenant = Tenant(
        name=payload.full_name or payload.email.split("@")[0],
        slug=str(uuid.uuid4()),
    )
    db.add(tenant)
    await db.flush()

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        tenant_id=tenant.id,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return await _issue_tokens(str(user.id), redis)


@router.post("/login", response_model=Token)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Token:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return await _issue_tokens(str(user.id), redis)


@router.post("/refresh", response_model=Token)
async def refresh(
    payload: RefreshRequest,
    redis: Redis = Depends(get_redis),
) -> Token:
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id: str = data["sub"]
        jti: str = data["jti"]
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    stored = await redis.get(f"{_REFRESH_PREFIX}{jti}")
    if stored != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or invalid"
        )

    await redis.delete(f"{_REFRESH_PREFIX}{jti}")
    return await _issue_tokens(user_id, redis)


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    redis: Redis = Depends(get_redis),
) -> None:
    try:
        data = decode_token(payload.refresh_token)
        jti = data.get("jti")
        if jti:
            await redis.delete(f"{_REFRESH_PREFIX}{jti}")
    except JWTError:
        pass


async def _issue_tokens(user_id: str, redis: Redis) -> Token:
    access_token = create_access_token(user_id)
    refresh_token, jti = create_refresh_token(user_id)
    ttl = settings.refresh_token_expire_days * 86400
    await redis.set(f"{_REFRESH_PREFIX}{jti}", user_id, ex=ttl)
    return Token(access_token=access_token, refresh_token=refresh_token)
