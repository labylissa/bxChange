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


@router.get("/", response_model=list[ExecutionRead])
async def list_executions(
    connector_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
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
        stmt = stmt.where(Execution.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Execution.created_at <= date_to)

    stmt = stmt.order_by(Execution.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    executions = result.scalars().all()
    return [ExecutionRead.model_validate(e) for e in executions]


@router.get("/{execution_id}", response_model=ExecutionRead)
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
