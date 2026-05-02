"""Tests for the admin license management API."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest_asyncio.fixture
async def super_admin(db_session: AsyncSession) -> User:
    user = User(
        email=f"sa-lic-{_uid()}@test.io",
        hashed_password=hash_password("sapass"),
        full_name="Super Admin",
        tenant_id=None,
        role="super_admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession, super_admin: User) -> tuple[Tenant, User]:
    tenant = Tenant(
        name="Test Corp",
        slug=f"test-corp-{_uid()}",
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
    )
    db_session.add(tenant)
    await db_session.flush()

    admin = User(
        email=f"admin-lic-{_uid()}@testcorp.io",
        hashed_password=hash_password("adminpass"),
        full_name="Corp Admin",
        tenant_id=tenant.id,
        role="admin",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant, admin


async def _sa_token(client: AsyncClient, super_admin: User) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": super_admin.email, "password": "sapass"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Create license ───────────────────────────────���─────────────────────────────

@patch("stripe.Customer.create", return_value=MagicMock(id="cus_test123"))
async def test_create_license(
    mock_stripe,
    client: AsyncClient,
    super_admin: User,
    test_tenant: tuple,
    db_session: AsyncSession,
):
    token = await _sa_token(client, super_admin)
    tenant, _ = test_tenant

    now = datetime.utcnow()
    r = await client.post(
        "/api/v1/admin/licenses",
        json={
            "tenant_id": str(tenant.id),
            "executions_limit": 5000,
            "connectors_limit": 10,
            "contract_start": now.isoformat(),
            "contract_end": (now + timedelta(days=365)).isoformat(),
            "annual_price_cents": 120000,
            "notes": "Contrat négocié",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["license_key"].startswith("bxc_lic_")
    assert data["executions_limit"] == 5000
    assert data["connectors_limit"] == 10
    assert data["status"] == "trial"

    # Tenant quotas updated
    await db_session.refresh(tenant)
    assert tenant.executions_limit == 5000
    assert tenant.connectors_limit == 10


# ── Activate license ─────────────────���─────────────────────────────────────────

@patch("stripe.Customer.create", return_value=MagicMock(id="cus_test456"))
async def test_activate_license(
    mock_stripe,
    client: AsyncClient,
    super_admin: User,
    test_tenant: tuple,
    db_session: AsyncSession,
):
    token = await _sa_token(client, super_admin)
    tenant, _ = test_tenant
    now = datetime.utcnow()

    # Create license first
    r = await client.post(
        "/api/v1/admin/licenses",
        json={
            "tenant_id": str(tenant.id),
            "executions_limit": 1000,
            "connectors_limit": 5,
            "contract_start": now.isoformat(),
            "contract_end": (now + timedelta(days=365)).isoformat(),
            "annual_price_cents": 50000,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    lic_id = r.json()["id"]

    # Activate it
    r2 = await client.post(
        f"/api/v1/admin/licenses/{lic_id}/activate",
        headers=_auth(token),
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "active"
    assert r2.json()["activated_at"] is not None

    await db_session.refresh(tenant)
    assert tenant.license_status == "active"


# ── Suspend license ────────────────────────────────��───────────────────────────

@patch("stripe.Customer.create", return_value=MagicMock(id="cus_test789"))
async def test_suspend_license(
    mock_stripe,
    client: AsyncClient,
    super_admin: User,
    test_tenant: tuple,
    db_session: AsyncSession,
):
    token = await _sa_token(client, super_admin)
    tenant, _ = test_tenant
    now = datetime.utcnow()

    r = await client.post(
        "/api/v1/admin/licenses",
        json={
            "tenant_id": str(tenant.id),
            "executions_limit": 1000,
            "connectors_limit": 5,
            "contract_start": now.isoformat(),
            "contract_end": (now + timedelta(days=365)).isoformat(),
            "annual_price_cents": 0,
        },
        headers=_auth(token),
    )
    lic_id = r.json()["id"]

    r2 = await client.post(
        f"/api/v1/admin/licenses/{lic_id}/suspend",
        json={"reason": "Non-paiement"},
        headers=_auth(token),
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["status"] == "suspended"
    assert data["suspension_reason"] == "Non-paiement"

    await db_session.refresh(tenant)
    assert tenant.license_status == "suspended"


# ── Non-super-admin cannot access ───────────────────────────��─────────────────

async def test_non_super_admin_cannot_list_licenses(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": f"reg-{_uid()}@test.com", "password": "TestPass1!", "full_name": "T"},
    )
    token = r.json()["access_token"]

    r2 = await client.get("/api/v1/admin/licenses", headers=_auth(token))
    assert r2.status_code == 403


# ── Tenant usage endpoint ────────────────────────────────���─────────────────────

async def test_get_tenant_usage(
    client: AsyncClient,
    super_admin: User,
    test_tenant: tuple,
    db_session: AsyncSession,
):
    token = await _sa_token(client, super_admin)
    tenant, _ = test_tenant
    tenant.executions_used = 42
    tenant.executions_limit = 1000
    await db_session.commit()

    r = await client.get(
        f"/api/v1/admin/tenants/{tenant.id}/usage",
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["executions_used"] == 42
    assert data["executions_limit"] == 1000
    assert data["executions_pct"] == 4.2
