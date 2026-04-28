"""Sprint 6 — Execution service + executions API tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connector import Connector
from app.models.execution import Execution


# ── Helpers ────────────────────────────────────────────────────────────────────

def _email() -> str:
    return f"{uuid.uuid4().hex[:8]}@test.com"


async def _register_login(client: AsyncClient) -> str:
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


async def _create_rest_connector(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/api/v1/connectors/",
        json={"name": "REST Test", "type": "rest", "base_url": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_soap_connector(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/api/v1/connectors/",
        json={"name": "SOAP Test", "type": "soap", "wsdl_url": "https://example.com/service?wsdl"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── 1. Execute SOAP connector ──────────────────────────────────────────────────

async def test_execute_soap_connector(client: AsyncClient):
    token = await _register_login(client)
    cid = await _create_soap_connector(client, token)

    with patch(
        "app.services.execution_service.soap_engine.execute",
        new_callable=AsyncMock,
        return_value={"AddResult": 8},
    ):
        r = await client.post(
            f"/api/v1/connectors/{cid}/execute",
            json={"params": {"operation": "Add", "intA": 5, "intB": 3}},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["result"] == {"AddResult": 8}
    assert "execution_id" in data
    assert data["duration_ms"] is not None


# ── 2. Execute REST connector ──────────────────────────────────────────────────

async def test_execute_rest_connector(client: AsyncClient):
    token = await _register_login(client)
    cid = await _create_rest_connector(client, token)

    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        return_value={"status_code": 200, "headers": {}, "body": {"user": "Alice"}},
    ):
        r = await client.post(
            f"/api/v1/connectors/{cid}/execute",
            json={"params": {"method": "GET", "path": "/users/1"}},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["result"] == {"user": "Alice"}


# ── 3. Execution saved on success ──────────────────────────────────────────────

async def test_execution_saved_on_success(client: AsyncClient, db_session: AsyncSession):
    token = await _register_login(client)
    cid = await _create_rest_connector(client, token)

    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        return_value={"status_code": 200, "headers": {}, "body": {"ok": True}},
    ):
        r = await client.post(
            f"/api/v1/connectors/{cid}/execute",
            json={"params": {}},
            headers={"Authorization": f"Bearer {token}"},
        )

    execution_id = r.json()["execution_id"]
    from sqlalchemy import select as sa_select
    result = await db_session.execute(
        sa_select(Execution).where(Execution.id == uuid.UUID(execution_id))
    )
    exc = result.scalar_one_or_none()
    assert exc is not None
    assert exc.status == "success"
    assert exc.triggered_by == "dashboard"
    assert exc.response_payload == {"ok": True}


# ── 4. Execution saved on engine error ────────────────────────────────────────

async def test_execution_saved_on_error(client: AsyncClient, db_session: AsyncSession):
    token = await _register_login(client)
    cid = await _create_rest_connector(client, token)

    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        side_effect=Exception("Connection refused"),
    ):
        r = await client.post(
            f"/api/v1/connectors/{cid}/execute",
            json={"params": {}},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "error"

    from sqlalchemy import select as sa_select
    result = await db_session.execute(
        sa_select(Execution).where(Execution.id == uuid.UUID(data["execution_id"]))
    )
    exc = result.scalar_one_or_none()
    assert exc is not None
    assert exc.status == "error"
    assert "Connection refused" in exc.error_message


# ── 5. Tenant isolation — connector of another tenant returns 404 ─────────────

async def test_execute_tenant_isolation(client: AsyncClient):
    token1 = await _register_login(client)
    token2 = await _register_login(client)
    cid = await _create_rest_connector(client, token1)

    r = await client.post(
        f"/api/v1/connectors/{cid}/execute",
        json={"params": {}},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r.status_code == 404


# ── 6. GET /executions — filter by status ────────────────────────────────────

async def test_list_executions_filter_status(client: AsyncClient):
    token = await _register_login(client)
    cid = await _create_rest_connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        return_value={"status_code": 200, "headers": {}, "body": {}},
    ):
        await client.post(f"/api/v1/connectors/{cid}/execute", json={"params": {}}, headers=headers)

    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        side_effect=Exception("boom"),
    ):
        await client.post(f"/api/v1/connectors/{cid}/execute", json={"params": {}}, headers=headers)

    r = await client.get("/api/v1/executions/?status=error", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert all(e["status"] == "error" for e in items)
    assert len(items) >= 1


# ── 7. GET /executions — filter by connector_id ───────────────────────────────

async def test_list_executions_filter_connector(client: AsyncClient):
    token = await _register_login(client)
    cid_a = await _create_rest_connector(client, token)
    cid_b = await _create_rest_connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        return_value={"status_code": 200, "headers": {}, "body": {"src": "A"}},
    ):
        await client.post(f"/api/v1/connectors/{cid_a}/execute", json={"params": {}}, headers=headers)
        await client.post(f"/api/v1/connectors/{cid_b}/execute", json={"params": {}}, headers=headers)

    r = await client.get(f"/api/v1/executions/?connector_id={cid_a}", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert all(e["connector_id"] == cid_a for e in items)
    assert len(items) >= 1


# ── 8. GET /executions/{id} — full detail ────────────────────────────────────

async def test_get_execution_detail(client: AsyncClient):
    token = await _register_login(client)
    cid = await _create_rest_connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        return_value={"status_code": 200, "headers": {}, "body": {"detail": "ok"}},
    ):
        r = await client.post(f"/api/v1/connectors/{cid}/execute", json={"params": {}}, headers=headers)

    execution_id = r.json()["execution_id"]
    r2 = await client.get(f"/api/v1/executions/{execution_id}", headers=headers)
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["id"] == execution_id
    assert detail["status"] == "success"
    assert detail["response_payload"] == {"detail": "ok"}
    assert "request_payload" in detail
    assert "created_at" in detail


# ── 9. GET /executions — pagination ──────────────────────────────────────────

async def test_list_executions_pagination(client: AsyncClient, db_session: AsyncSession):
    token = await _register_login(client)
    cid = await _create_rest_connector(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    # Insert 12 execution records directly into the DB
    connector_uuid = uuid.UUID(cid)
    for _ in range(12):
        db_session.add(
            Execution(
                connector_id=connector_uuid,
                status="success",
                duration_ms=10,
                triggered_by="dashboard",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
    await db_session.commit()

    r1 = await client.get(f"/api/v1/executions/?connector_id={cid}&page=1&page_size=5", headers=headers)
    assert r1.status_code == 200
    assert len(r1.json()) == 5

    r2 = await client.get(f"/api/v1/executions/?connector_id={cid}&page=2&page_size=5", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()) == 5

    # page 3 should have the remaining 2
    r3 = await client.get(f"/api/v1/executions/?connector_id={cid}&page=3&page_size=5", headers=headers)
    assert r3.status_code == 200
    assert len(r3.json()) == 2

    # ids on page 1 and page 2 must be disjoint
    ids1 = {e["id"] for e in r1.json()}
    ids2 = {e["id"] for e in r2.json()}
    assert ids1.isdisjoint(ids2)
