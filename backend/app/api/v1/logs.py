"""Logs API — metrics, recent executions, errors, and alerts."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.connector import Connector
from app.models.execution import Execution
from app.models.user import User
from app.services import metrics_service

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/metrics")
async def get_metrics(
    period: str = Query(default="24h"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if period not in ("24h", "7d", "30d"):
        period = "24h"
    return await metrics_service.compute_metrics(current_user.tenant_id, period, db)


@router.get("/recent")
async def get_recent(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rows = (
        await db.execute(
            select(
                Execution.id,
                Connector.name.label("connector_name"),
                Execution.status,
                Execution.duration_ms,
                Execution.http_status,
                Execution.created_at,
            )
            .join(Connector, Execution.connector_id == Connector.id)
            .where(Connector.tenant_id == current_user.tenant_id)
            .order_by(Execution.created_at.desc())
            .limit(50)
        )
    ).all()
    return [
        {
            "id": str(row.id),
            "connector_name": row.connector_name,
            "status": row.status,
            "duration_ms": row.duration_ms,
            "http_status": row.http_status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/errors")
async def get_errors(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    since_24h = datetime.utcnow() - timedelta(hours=24)
    rows = (
        await db.execute(
            select(
                Execution.id,
                Connector.name.label("connector_name"),
                Execution.status,
                Execution.duration_ms,
                Execution.error_message,
                Execution.created_at,
            )
            .join(Connector, Execution.connector_id == Connector.id)
            .where(
                Connector.tenant_id == current_user.tenant_id,
                Execution.status.in_(["error", "timeout"]),
                Execution.created_at >= since_24h,
            )
            .order_by(Execution.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "id": str(row.id),
            "connector_name": row.connector_name,
            "status": row.status,
            "duration_ms": row.duration_ms,
            "error_message": row.error_message,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/alerts")
async def get_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await metrics_service.compute_alerts(current_user.tenant_id, db)
