"""Sprint 7 — Logs & Metrics API tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution


# ── Helpers ────────────────────────────────────────────────────────────────────

def _email() -> str:
    return f"{uuid.uuid4().hex[:8]}@test.com"


async def _auth(client: AsyncClient) -> str:
    email = _email()
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass1!", "full_name": "T"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass1!"},
    )
    return r.json()["access_token"]


async def _connector(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/api/v1/connectors",
        json={
            "name": f"C-{uuid.uuid4().hex[:6]}",
            "type": "rest",
            "base_url": "https://api.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _make_exec(
    connector_id: str,
    status: str = "success",
    duration_ms: int = 100,
    error_msg: str | None = None,
    hours_ago: float = 0,
    request_payload: dict | None = None,
    response_payload: dict | None = None,
) -> Execution:
    return Execution(
        connector_id=uuid.UUID(connector_id),
        status=status,
        duration_ms=duration_ms,
        triggered_by="dashboard",
        error_message=error_msg,
        created_at=datetime.utcnow() - timedelta(hours=hours_ago),
        request_payload=request_payload,
        response_payload=response_payload,
    )


# ── 1. GET /metrics — 24h structure ───────────────────────────────────────────

async def test_metrics_24h_structure(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    cid = await _connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    db_session.add_all([
        _make_exec(cid, status="success", duration_ms=200),
        _make_exec(cid, status="error", duration_ms=50, error_msg="boom"),
    ])
    await db_session.commit()

    r = await client.get("/api/v1/logs/metrics?period=24h", headers=headers)
    assert r.status_code == 200
    data = r.json()

    assert "total_calls" in data
    assert "success_count" in data
    assert "error_count" in data
    assert "success_rate" in data
    assert "avg_duration_ms" in data
    assert "p95_duration_ms" in data
    assert "calls_by_hour" in data
    assert "calls_by_connector" in data
    assert "calls_by_status" in data

    assert data["total_calls"] >= 2
    assert data["success_count"] >= 1
    assert data["error_count"] >= 1
    assert isinstance(data["success_rate"], float)
    assert isinstance(data["calls_by_status"], dict)
    assert set(data["calls_by_status"].keys()) == {"success", "error", "timeout"}


# ── 2. GET /metrics — 7d period filters correctly ─────────────────────────────

async def test_metrics_7d_period(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    cid = await _connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    # 2 executions within 7 days, 1 older than 7 days
    db_session.add_all([
        _make_exec(cid, status="success", hours_ago=2),
        _make_exec(cid, status="success", hours_ago=100),   # ~4 days ago
        _make_exec(cid, status="error", hours_ago=200),     # ~8 days ago — excluded
    ])
    await db_session.commit()

    r = await client.get("/api/v1/logs/metrics?period=7d", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_calls"] == 2
    assert data["success_count"] == 2
    assert data["error_count"] == 0


# ── 3. calls_by_hour — always 24 entries ──────────────────────────────────────

async def test_calls_by_hour_24_entries(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    cid = await _connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    db_session.add(_make_exec(cid))
    await db_session.commit()

    r = await client.get("/api/v1/logs/metrics", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["calls_by_hour"]) == 24


# ── 4. calls_by_connector — top 10 max ────────────────────────────────────────

async def test_calls_by_connector_top10(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create 11 connectors, 1 execution each
    for _ in range(11):
        cid = await _connector(client, token)
        db_session.add(_make_exec(cid))
    await db_session.commit()

    r = await client.get("/api/v1/logs/metrics", headers=headers)
    assert r.status_code == 200
    items = r.json()["calls_by_connector"]
    assert len(items) <= 10
    for item in items:
        assert "connector_id" in item
        assert "name" in item
        assert "count" in item
        assert "error_rate" in item


# ── 5. GET /recent — max 50, no payloads ─────────────────────────────────────

async def test_recent_50_max_no_payloads(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    cid = await _connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(60):
        db_session.add(
            _make_exec(
                cid,
                hours_ago=i * 0.01,
                request_payload={"params": {}},
                response_payload={"result": "ok"},
            )
        )
    await db_session.commit()

    r = await client.get("/api/v1/logs/recent", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) <= 50
    for item in items:
        assert "request_payload" not in item
        assert "response_payload" not in item
        assert "id" in item
        assert "connector_name" in item
        assert "status" in item
        assert "created_at" in item


# ── 6. GET /errors — only errors within 24 h ─────────────────────────────────

async def test_errors_only_last_24h(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    cid = await _connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    db_session.add_all([
        _make_exec(cid, status="success", hours_ago=1),
        _make_exec(cid, status="error", hours_ago=1, error_msg="recent error"),
        _make_exec(cid, status="error", hours_ago=30, error_msg="old error"),  # excluded
    ])
    await db_session.commit()

    r = await client.get("/api/v1/logs/errors", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert all(i["status"] in ("error", "timeout") for i in items)
    messages = [i["error_message"] for i in items]
    assert "recent error" in messages
    assert "old error" not in messages
    assert len(items) <= 100


# ── 7. GET /alerts — high_error_rate detected ────────────────────────────────

async def test_alerts_high_error_rate(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    cid = await _connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    # 3 success, 7 errors = 70% error rate in last 1h
    db_session.add_all([
        *[_make_exec(cid, status="success", hours_ago=0.1) for _ in range(3)],
        *[_make_exec(cid, status="error", error_msg="x", hours_ago=0.1) for _ in range(7)],
    ])
    await db_session.commit()

    r = await client.get("/api/v1/logs/alerts", headers=headers)
    assert r.status_code == 200
    alerts = r.json()
    types = [a["type"] for a in alerts]
    assert "high_error_rate" in types

    alert = next(a for a in alerts if a["type"] == "high_error_rate")
    assert alert["connector_id"] == cid
    assert alert["value"] > 0.20
    assert alert["threshold"] == 0.20


# ── 8. GET /alerts — slow_response detected ───────────────────────────────────

async def test_alerts_slow_response(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    cid = await _connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    # 20 executions with p95 duration of 6000ms (all at 6000ms → p95 = 6000)
    db_session.add_all([
        _make_exec(cid, status="success", duration_ms=6000, hours_ago=0.1)
        for _ in range(20)
    ])
    await db_session.commit()

    r = await client.get("/api/v1/logs/alerts", headers=headers)
    assert r.status_code == 200
    alerts = r.json()
    types = [a["type"] for a in alerts]
    assert "slow_response" in types

    alert = next(a for a in alerts if a["type"] == "slow_response")
    assert alert["connector_id"] == cid
    assert alert["value"] > 5000
    assert alert["threshold"] == 5000


# ── 9. GET /alerts — empty when nominal ───────────────────────────────────────

async def test_alerts_nominal_empty(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    cid = await _connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    # All success, fast responses, error rate = 0%
    db_session.add_all([
        _make_exec(cid, status="success", duration_ms=100, hours_ago=0.1)
        for _ in range(10)
    ])
    await db_session.commit()

    r = await client.get("/api/v1/logs/alerts", headers=headers)
    assert r.status_code == 200
    # This tenant's connector is nominal; there should be no alerts for it
    alerts = [a for a in r.json() if a["connector_id"] == cid]
    assert alerts == []


# ── 10. Tenant isolation ──────────────────────────────────────────────────────

async def test_tenant_isolation(client: AsyncClient, db_session: AsyncSession):
    token1 = await _auth(client)
    token2 = await _auth(client)

    cid1 = await _connector(client, token1)
    cid2 = await _connector(client, token2)

    # Tenant 1: 5 executions; Tenant 2: 3 executions
    db_session.add_all([_make_exec(cid1) for _ in range(5)])
    db_session.add_all([_make_exec(cid2) for _ in range(3)])
    await db_session.commit()

    r1 = await client.get(
        "/api/v1/logs/metrics",
        headers={"Authorization": f"Bearer {token1}"},
    )
    r2 = await client.get(
        "/api/v1/logs/metrics",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    data1 = r1.json()
    data2 = r2.json()

    # Each tenant sees only their own executions
    cids1 = {c["connector_id"] for c in data1["calls_by_connector"]}
    cids2 = {c["connector_id"] for c in data2["calls_by_connector"]}
    assert cid1 in cids1
    assert cid2 not in cids1
    assert cid2 in cids2
    assert cid1 not in cids2
