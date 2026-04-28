"""API Keys endpoints — list, create, revoke."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services import api_key_service

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("/", response_model=list[ApiKeyRead])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyRead]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.tenant_id == current_user.tenant_id)
    )
    return [ApiKeyRead.model_validate(k) for k in result.scalars().all()]


@router.post("/", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    return await api_key_service.create_api_key(current_user.tenant_id, payload, db)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.tenant_id == current_user.tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.is_active = False
    await db.commit()
