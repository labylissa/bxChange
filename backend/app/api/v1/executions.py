"""Executions API — list and detail endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.connector import Connector
from app.models.execution import Execution
from app.models.user import User
from app.schemas.execution import ExecutionRead

router = APIRouter(prefix="/executions", tags=["executions"])

_401 = {"description": "Token invalide ou expiré"}
_404 = {"description": "Exécution introuvable"}


@router.get(
    "/",
    response_model=list[ExecutionRead],
    summary="Historique des exécutions",
    description=(
        "Retourne l'historique paginé des exécutions du tenant. "
        "Filtres disponibles : `connector_id`, `status` (success/error/timeout/pending), "
        "`date_from`, `date_to`. Tri anti-chronologique."
    ),
    responses={
        200: {"description": "Liste paginée des exécutions"},
        401: _401,
    },
)
async def list_executions(
    connector_id: uuid.UUID | None = Query(default=None, description="Filtrer par connecteur"),
    status_filter: str | None = Query(
        default=None, alias="status",
        description="Filtrer par statut : success | error | timeout | pending",
    ),
    date_from: datetime | None = Query(default=None, description="Début de période (ISO 8601)"),
    date_to: datetime | None = Query(default=None, description="Fin de période (ISO 8601)"),
    page: int = Query(default=1, ge=1, description="Numéro de page"),
    page_size: int = Query(default=20, ge=1, le=100, description="Résultats par page (max 100)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExecutionRead]:
    stmt = (
        select(Execution)
        .join(Connector, Execution.connector_id == Connector.id)
        .where(Connector.tenant_id == current_user.tenant_id)
    )

    if connector_id is not None:
        stmt = stmt.where(Execution.connector_id == connector_id)
    if status_filter is not None:
        stmt = stmt.where(Execution.status == status_filter)
    if date_from is not None:
        df = date_from.replace(tzinfo=None) if date_from.tzinfo else date_from
        stmt = stmt.where(Execution.created_at >= df)
    if date_to is not None:
        dt = date_to.replace(tzinfo=None) if date_to.tzinfo else date_to
        stmt = stmt.where(Execution.created_at <= dt)

    stmt = stmt.order_by(Execution.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    executions = result.scalars().all()
    return [ExecutionRead.model_validate(e) for e in executions]


@router.get(
    "/{execution_id}",
    response_model=ExecutionRead,
    summary="Détail d'une exécution",
    description=(
        "Retourne le détail complet d'une exécution : payload de requête, "
        "réponse JSON, durée, statut HTTP, message d'erreur éventuel."
    ),
    responses={
        200: {"description": "Détail de l'exécution"},
        401: _401,
        404: _404,
    },
)
async def get_execution(
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionRead:
    stmt = (
        select(Execution)
        .join(Connector, Execution.connector_id == Connector.id)
        .where(
            Execution.id == execution_id,
            Connector.tenant_id == current_user.tenant_id,
        )
    )
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return ExecutionRead.model_validate(execution)
