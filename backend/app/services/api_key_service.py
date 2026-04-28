"""API Key service — generation, validation, and per-hour rate limiting."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead


def generate_key() -> tuple[str, str]:
    """Return (raw_key, key_hash). raw_key is prefixed with 'bxc_'."""
    raw_key = "bxc_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def create_api_key(
    tenant_id: uuid.UUID,
    data: ApiKeyCreate,
    db: AsyncSession,
) -> ApiKeyCreated:
    raw_key, key_hash = generate_key()
    api_key = ApiKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        name=data.name,
        permissions=data.permissions,
        rate_limit=data.rate_limit,
        expires_at=data.expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    base = ApiKeyRead.model_validate(api_key)
    return ApiKeyCreated(**base.model_dump(), raw_key=raw_key)


async def validate_api_key(raw_key: str, db: AsyncSession) -> ApiKey | None:
    """Hash raw_key, look it up, check active + not expired. Returns None on any failure."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()
    if api_key is None or not api_key.is_active:
        return None
    if api_key.expires_at is not None and api_key.expires_at < datetime.utcnow():
        return None
    return api_key


async def check_rate_limit(api_key: ApiKey, redis) -> bool:
    """Increment hourly counter in Redis. Returns False when limit is exceeded."""
    if api_key.rate_limit is None:
        return True
    now = datetime.utcnow()
    hour_key = f"ratelimit:{api_key.id}:{now.strftime('%Y%m%d%H')}"
    count = await redis.incr(hour_key)
    if count == 1:
        await redis.expire(hour_key, 3600)
    return int(count) <= api_key.rate_limit
