"""Metrics service — aggregated connector execution stats for the dashboard."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connector import Connector
from app.models.execution import Execution

_PERIODS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _error_case():
    """CASE expression: 1 for error/timeout rows, else 0."""
    return case((Execution.status.in_(["error", "timeout"]), 1), else_=0)


def _percentile(values: list, pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(pct * len(sorted_vals))
    return float(sorted_vals[min(idx, len(sorted_vals) - 1)])


async def compute_metrics(tenant_id: uuid.UUID, period: str, db: AsyncSession) -> dict:
    delta = _PERIODS.get(period, timedelta(hours=24))
    now = datetime.utcnow()
    since = now - delta
    since_24h = now - timedelta(hours=24)

    # ── Aggregate totals (single SQL round-trip) ──────────────────────────
    agg = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(case((Execution.status == "success", 1), else_=0)).label("success"),
                func.sum(case((Execution.status == "error", 1), else_=0)).label("error"),
                func.sum(case((Execution.status == "timeout", 1), else_=0)).label("timeout"),
                func.avg(Execution.duration_ms).label("avg_dur"),
            )
            .join(Connector, Execution.connector_id == Connector.id)
            .where(Connector.tenant_id == tenant_id, Execution.created_at >= since)
        )
    ).one()

    total = agg.total or 0
    success = agg.success or 0
    error = agg.error or 0
    timeout = agg.timeout or 0
    avg_dur = float(agg.avg_dur or 0.0)
    success_rate = round(success / total * 100, 2) if total else 0.0

    # ── p95 duration — Python sort (SQLite-compatible; prod uses PostgreSQL) ─
    durations = (
        await db.execute(
            select(Execution.duration_ms)
            .join(Connector, Execution.connector_id == Connector.id)
            .where(
                Connector.tenant_id == tenant_id,
                Execution.created_at >= since,
                Execution.duration_ms.isnot(None),
            )
        )
    ).scalars().all()
    p95 = _percentile(list(durations), 0.95)

    # ── calls_by_hour — always last 24 h, 24 pre-filled slots ────────────
    now_hour = now.replace(minute=0, second=0, microsecond=0)
    slots: dict[str, dict] = {}
    for i in range(23, -1, -1):
        slot_dt = now_hour - timedelta(hours=i)
        key = slot_dt.strftime("%Y-%m-%dT%H:00")
        slots[key] = {"hour": key, "count": 0, "errors": 0}

    hourly = (
        await db.execute(
            select(Execution.created_at, Execution.status)
            .join(Connector, Execution.connector_id == Connector.id)
            .where(Connector.tenant_id == tenant_id, Execution.created_at >= since_24h)
        )
    ).all()
    for (created_at, status) in hourly:
        key = created_at.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00")
        if key in slots:
            slots[key]["count"] += 1
            if status in ("error", "timeout"):
                slots[key]["errors"] += 1

    calls_by_hour = list(slots.values())

    # ── calls_by_connector — top 10 by volume ────────────────────────────
    connector_rows = (
        await db.execute(
            select(
                Execution.connector_id,
                Connector.name,
                func.count().label("count"),
                func.sum(_error_case()).label("errors"),
            )
            .join(Connector, Execution.connector_id == Connector.id)
            .where(Connector.tenant_id == tenant_id, Execution.created_at >= since)
            .group_by(Execution.connector_id, Connector.name)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    calls_by_connector = [
        {
            "connector_id": str(row.connector_id),
            "name": row.name,
            "count": row.count,
            "error_rate": round(row.errors / row.count * 100, 2) if row.count else 0.0,
        }
        for row in connector_rows
    ]

    return {
        "total_calls": total,
        "success_count": success,
        "error_count": error,
        "success_rate": success_rate,
        "avg_duration_ms": round(avg_dur, 2),
        "p95_duration_ms": p95,
        "calls_by_hour": calls_by_hour,
        "calls_by_connector": calls_by_connector,
        "calls_by_status": {"success": success, "error": error, "timeout": timeout},
    }


async def compute_alerts(tenant_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    since_1h = datetime.utcnow() - timedelta(hours=1)
    alerts: list[dict] = []

    # ── Error-rate alert: >20% errors in last 1 h per connector ──────────
    err_rows = (
        await db.execute(
            select(
                Execution.connector_id,
                Connector.name,
                func.count().label("count"),
                func.sum(_error_case()).label("errors"),
                func.min(Execution.created_at).label("since"),
            )
            .join(Connector, Execution.connector_id == Connector.id)
            .where(Connector.tenant_id == tenant_id, Execution.created_at >= since_1h)
            .group_by(Execution.connector_id, Connector.name)
        )
    ).all()

    for row in err_rows:
        error_rate = row.errors / row.count if row.count else 0.0
        if error_rate > 0.20:
            alerts.append(
                {
                    "type": "high_error_rate",
                    "connector_id": str(row.connector_id),
                    "connector_name": row.name,
                    "value": round(error_rate, 4),
                    "threshold": 0.20,
                    "since": row.since.isoformat() if row.since else None,
                }
            )

    # ── Slow-response alert: p95 > 5000 ms in last 1 h per connector ─────
    dur_rows = (
        await db.execute(
            select(Execution.connector_id, Connector.name, Execution.duration_ms)
            .join(Connector, Execution.connector_id == Connector.id)
            .where(
                Connector.tenant_id == tenant_id,
                Execution.created_at >= since_1h,
                Execution.duration_ms.isnot(None),
            )
        )
    ).all()

    dur_map: dict[str, list[int]] = {}
    name_map: dict[str, str] = {}
    for row in dur_rows:
        cid = str(row.connector_id)
        dur_map.setdefault(cid, []).append(row.duration_ms)
        name_map[cid] = row.name

    for cid, durs in dur_map.items():
        p95 = _percentile(durs, 0.95)
        if p95 > 5000:
            alerts.append(
                {
                    "type": "slow_response",
                    "connector_id": cid,
                    "connector_name": name_map[cid],
                    "value": float(p95),
                    "threshold": 5000,
                    "since": since_1h.isoformat(),
                }
            )

    return alerts
