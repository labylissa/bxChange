"""Tests for license/quota enforcement on the execute endpoint."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant


def _email() -> str:
    return f"lic_{uuid.uuid4().hex[:8]}@test.com"


async def _register_and_setup(client: AsyncClient) -> tuple[str, str, str]:
    """Register user, return (token, tenant_id, connector_id)."""
    email = _email()
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass1!", "full_name": "T"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenant_id"]

    rc = await client.post(
        "/api/v1/connectors",
        json={"name": "Test REST", "type": "rest", "base_url": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rc.status_code == 201
    connector_id = rc.json()["id"]

    return token, tenant_id, connector_id


async def _get_tenant(db: AsyncSession, tenant_id: str) -> Tenant:
    return (await db.execute(
        select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
    )).scalar_one()


# ── Quota bloqué ──────────────────────────────────────────────────────────────

async def test_quota_exceeded_blocks_execution(
    client: AsyncClient, db_session: AsyncSession
):
    token, tenant_id, connector_id = await _register_and_setup(client)

    tenant = await _get_tenant(db_session, tenant_id)
    tenant.executions_used = tenant.executions_limit
    await db_session.commit()

    with patch("app.services.rest_engine.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"status_code": 200, "body": {}, "headers": {}}
        r = await client.post(
            f"/api/v1/connectors/{connector_id}/execute",
            json={"params": {}},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 402
    assert "Quota mensuel atteint" in r.json()["detail"]


# ── Licence expirée ───────────────────────────────────────────────────────────

async def test_expired_license_blocks_execution(
    client: AsyncClient, db_session: AsyncSession
):
    token, tenant_id, connector_id = await _register_and_setup(client)

    tenant = await _get_tenant(db_session, tenant_id)
    tenant.license_status = "expired"
    await db_session.commit()

    r = await client.post(
        f"/api/v1/connectors/{connector_id}/execute",
        json={"params": {}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 402
    assert "expiré" in r.json()["detail"]


# ── Licence suspendue ─────────────────────────────────────────────────────────

async def test_suspended_license_blocks_execution(
    client: AsyncClient, db_session: AsyncSession
):
    token, tenant_id, connector_id = await _register_and_setup(client)

    tenant = await _get_tenant(db_session, tenant_id)
    tenant.license_status = "suspended"
    await db_session.commit()

    r = await client.post(
        f"/api/v1/connectors/{connector_id}/execute",
        json={"params": {}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 402
    assert "suspendue" in r.json()["detail"]


# ── Trial expiré auto ─────────────────────────────────────────────────────────

async def test_expired_trial_blocks_execution(
    client: AsyncClient, db_session: AsyncSession
):
    token, tenant_id, connector_id = await _register_and_setup(client)

    tenant = await _get_tenant(db_session, tenant_id)
    tenant.license_status = "trial"
    tenant.trial_ends_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()

    r = await client.post(
        f"/api/v1/connectors/{connector_id}/execute",
        json={"params": {}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 402
    assert "essai" in r.json()["detail"].lower()


# ── Quota OK → exécution réussie ──────────────────────────────────────────────

async def test_active_license_allows_execution(
    client: AsyncClient, db_session: AsyncSession
):
    token, tenant_id, connector_id = await _register_and_setup(client)

    tenant = await _get_tenant(db_session, tenant_id)
    tenant.license_status = "active"
    tenant.executions_used = 0
    tenant.executions_limit = 1000
    await db_session.commit()

    with patch("app.services.rest_engine.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"status_code": 200, "body": {"ok": True}, "headers": {}}
        r = await client.post(
            f"/api/v1/connectors/{connector_id}/execute",
            json={"params": {}},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
