"""Permission and role tests — Sprint 12."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.connector import Connector
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User


def _uid() -> str:
    """Short unique suffix so emails don't collide across tests in the shared SQLite DB."""
    return uuid.uuid4().hex[:8]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def super_admin(db_session: AsyncSession):
    user = User(
        email=f"sa-{_uid()}@test.io",
        hashed_password=hash_password("superpass"),
        full_name="Super Admin",
        tenant_id=None,
        role="super_admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def tenant_with_subscription(db_session: AsyncSession):
    slug = f"acme-{_uid()}"
    tenant = Tenant(name="Acme Corp", slug=slug)
    db_session.add(tenant)
    await db_session.flush()

    sub = Subscription(
        tenant_id=tenant.id,
        plan="starter",
        status="active",
        connector_limit=2,
        users_limit=3,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant, sub


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, tenant_with_subscription):
    tenant, _ = tenant_with_subscription
    user = User(
        email=f"admin-{_uid()}@acme-test.io",
        hashed_password=hash_password("adminpass"),
        full_name="Acme Admin",
        tenant_id=tenant.id,
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def developer_user(db_session: AsyncSession, tenant_with_subscription):
    tenant, _ = tenant_with_subscription
    user = User(
        email=f"dev-{_uid()}@acme-test.io",
        hashed_password=hash_password("devpass"),
        full_name="Acme Dev",
        tenant_id=tenant.id,
        role="developer",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def viewer_user(db_session: AsyncSession, tenant_with_subscription):
    tenant, _ = tenant_with_subscription
    user = User(
        email=f"viewer-{_uid()}@acme-test.io",
        hashed_password=hash_password("viewpass"),
        full_name="Acme Viewer",
        tenant_id=tenant.id,
        role="viewer",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ── helper: login using user object ───────────────────────────────────────────

async def _token_for(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ── super_admin tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_super_admin_can_list_tenants(client: AsyncClient, super_admin: User):
    token = await _token_for(client, super_admin.email, "superpass")
    r = await client.get("/api/v1/admin/tenants", headers=_auth(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_super_admin_can_create_tenant(client: AsyncClient, super_admin: User):
    token = await _token_for(client, super_admin.email, "superpass")
    new_email = f"admin-beta-{_uid()}@test.io"
    r = await client.post("/api/v1/admin/tenants", json={
        "company_name": "BetaCorp",
        "admin_email": new_email,
        "admin_name": "Beta Admin",
        "admin_password": "betapass",
        "connector_limit": 5,
        "users_limit": 3,
    }, headers=_auth(token))
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "BetaCorp"
    assert data["connector_limit"] == 5
    assert data["users_limit"] == 3


@pytest.mark.asyncio
async def test_non_super_admin_cannot_access_admin_routes(client: AsyncClient, admin_user: User):
    token = await _token_for(client, admin_user.email, "adminpass")
    r = await client.get("/api/v1/admin/tenants", headers=_auth(token))
    assert r.status_code == 403


# ── admin (tenant admin) tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_invite_user(client: AsyncClient, admin_user: User):
    token = await _token_for(client, admin_user.email, "adminpass")
    r = await client.post("/api/v1/team/invite", json={
        "email": f"newdev-{_uid()}@acme-test.io",
        "full_name": "New Dev",
        "password": "newdevpass",
        "role": "developer",
    }, headers=_auth(token))
    assert r.status_code == 201
    assert r.json()["role"] == "developer"


@pytest.mark.asyncio
async def test_admin_cannot_see_other_tenant(client: AsyncClient, admin_user: User):
    token = await _token_for(client, admin_user.email, "adminpass")
    r = await client.get("/api/v1/admin/tenants", headers=_auth(token))
    assert r.status_code == 403


# ── developer tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_developer_cannot_manage_users(client: AsyncClient, developer_user: User):
    token = await _token_for(client, developer_user.email, "devpass")
    r = await client.get("/api/v1/team/members", headers=_auth(token))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_developer_cannot_invite(client: AsyncClient, developer_user: User):
    token = await _token_for(client, developer_user.email, "devpass")
    r = await client.post("/api/v1/team/invite", json={
        "email": f"x-{_uid()}@x.io", "full_name": "X", "password": "xpass", "role": "viewer"
    }, headers=_auth(token))
    assert r.status_code == 403


# ── viewer tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_viewer_can_authenticate(client: AsyncClient, viewer_user: User):
    token = await _token_for(client, viewer_user.email, "viewpass")
    r = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"


# ── connector quota tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connector_quota_blocks_creation(
    client: AsyncClient,
    admin_user: User,
    tenant_with_subscription,
    db_session: AsyncSession,
):
    tenant, _sub = tenant_with_subscription
    # connector_limit = 2 — fill it up
    for i in range(2):
        c = Connector(
            tenant_id=tenant.id,
            name=f"Quota Test {i} {_uid()}",
            type="rest",
            auth_type="none",
            status="active",
            created_by=admin_user.id,
        )
        db_session.add(c)
    await db_session.commit()

    token = await _token_for(client, admin_user.email, "adminpass")
    r = await client.post("/api/v1/connectors/", json={
        "name": "Over quota",
        "type": "rest",
        "base_url": "https://example.com",
        "auth_type": "none",
    }, headers=_auth(token))
    assert r.status_code == 403
    assert "Quota atteint" in r.json()["detail"]


# ── user quota tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_quota_blocks_invite(
    client: AsyncClient,
    admin_user: User,
    tenant_with_subscription,
    db_session: AsyncSession,
):
    tenant, _sub = tenant_with_subscription
    # users_limit = 3 — admin_user is 1, add 2 more to hit the cap
    for _ in range(2):
        u = User(
            email=f"extra-{_uid()}@acme-test.io",
            hashed_password=hash_password("pass"),
            tenant_id=tenant.id,
            role="viewer",
        )
        db_session.add(u)
    await db_session.commit()

    token = await _token_for(client, admin_user.email, "adminpass")
    r = await client.post("/api/v1/team/invite", json={
        "email": f"overflow-{_uid()}@acme-test.io",
        "full_name": "Overflow",
        "password": "overpass",
        "role": "viewer",
    }, headers=_auth(token))
    assert r.status_code == 403
    assert "Quota atteint" in r.json()["detail"]


# ── impersonation tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_impersonation_token_valid(
    client: AsyncClient,
    super_admin: User,
    admin_user: User,
):
    sa_token = await _token_for(client, super_admin.email, "superpass")
    r = await client.post(
        f"/api/v1/admin/impersonate/{admin_user.id}",
        headers=_auth(sa_token),
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["expires_in"] == 3600

    # Verify the impersonation token authenticates as the target user
    r2 = await client.get("/api/v1/auth/me", headers=_auth(data["access_token"]))
    assert r2.status_code == 200
    assert r2.json()["email"] == admin_user.email
