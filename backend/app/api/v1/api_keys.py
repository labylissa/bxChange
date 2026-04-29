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

_401 = {"description": "Token invalide ou expiré"}
_404 = {"description": "Clé API introuvable"}


@router.get(
    "",
    response_model=list[ApiKeyRead],
    summary="Lister les clés API",
    description="Retourne toutes les clés API du tenant (actives et révoquées). La valeur brute n'est jamais retournée.",
    responses={200: {"description": "Liste des clés API"}, 401: _401},
)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyRead]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.tenant_id == current_user.tenant_id)
    )
    return [ApiKeyRead.model_validate(k) for k in result.scalars().all()]


@router.post(
    "",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une clé API",
    description=(
        "Génère une nouvelle clé API avec préfixe `bxc_`. "
        "La valeur brute (`raw_key`) est retournée **une seule fois** à la création — "
        "elle ne peut pas être récupérée ensuite. Conservez-la en lieu sûr."
    ),
    responses={
        201: {"description": "Clé créée — raw_key affiché une seule fois"},
        401: _401,
    },
)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    return await api_key_service.create_api_key(current_user.tenant_id, payload, db)


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Révoquer une clé API",
    description="Désactive la clé API. Les appels utilisant cette clé seront immédiatement rejetés (401).",
    responses={
        204: {"description": "Clé révoquée"},
        401: _401,
        404: _404,
    },
)
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
