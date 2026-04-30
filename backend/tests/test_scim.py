"""Sprint 18 — SCIM 2.0 tests."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scim_token import ScimToken
from app.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _email() -> str:
    return f"{uuid.uuid4().hex[:8]}@scim-test.com"


async def _create_scim_token(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Insert a ScimToken and return the raw bearer value."""
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token = ScimToken(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        token_hash=token_hash,
        name="test-scim-token",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(token)
    await db.commit()
    return raw


async def _register_user(client: AsyncClient, db: AsyncSession, email: str | None = None) -> tuple[str, uuid.UUID]:
    """Register a user, return (access_token, tenant_id)."""
    email = email or _email()
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass1!", "full_name": "SCIM Test"},
    )
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass1!"})
    token = r.json()["access_token"]

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    return token, user.tenant_id


def _scim_headers(raw_token: str) -> dict:
    return {"Authorization": f"Bearer {raw_token}", "Content-Type": "application/scim+json"}


# ── 1. Auth ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scim_no_token_returns_401(client: AsyncClient):
    r = await client.get("/api/v1/scim/v2/Users")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_scim_invalid_token_returns_401(client: AsyncClient):
    r = await client.get(
        "/api/v1/scim/v2/Users",
        headers={"Authorization": "Bearer totallyinvalidtoken"},
    )
    assert r.status_code == 401


# ── 2. List users ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scim_list_users(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    r = await client.get("/api/v1/scim/v2/Users", headers=_scim_headers(raw))
    assert r.status_code == 200
    data = r.json()
    assert "totalResults" in data
    assert "Resources" in data
    assert data["totalResults"] >= 1


# ── 3. Create user ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scim_create_user(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    new_email = _email()
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": new_email,
        "name": {"givenName": "John", "familyName": "Doe"},
        "emails": [{"value": new_email, "type": "work", "primary": True}],
        "active": True,
    }
    r = await client.post("/api/v1/scim/v2/Users", json=payload, headers=_scim_headers(raw))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["userName"] == new_email
    assert data["active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_scim_create_user_duplicate_returns_409(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    email = _email()
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": email,
        "emails": [{"value": email, "type": "work", "primary": True}],
        "active": True,
    }
    r1 = await client.post("/api/v1/scim/v2/Users", json=payload, headers=_scim_headers(raw))
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/scim/v2/Users", json=payload, headers=_scim_headers(raw))
    assert r2.status_code == 409


# ── 4. Get user ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scim_get_user(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    new_email = _email()
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": new_email,
        "emails": [{"value": new_email, "primary": True}],
        "active": True,
    }
    create_r = await client.post("/api/v1/scim/v2/Users", json=payload, headers=_scim_headers(raw))
    user_id = create_r.json()["id"]

    r = await client.get(f"/api/v1/scim/v2/Users/{user_id}", headers=_scim_headers(raw))
    assert r.status_code == 200
    assert r.json()["id"] == user_id


@pytest.mark.asyncio
async def test_scim_get_user_not_found(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    r = await client.get(f"/api/v1/scim/v2/Users/{uuid.uuid4()}", headers=_scim_headers(raw))
    assert r.status_code == 404


# ── 5. Update user (PUT) ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scim_put_user_deactivate(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    new_email = _email()
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": new_email,
        "emails": [{"value": new_email, "primary": True}],
        "active": True,
    }
    create_r = await client.post("/api/v1/scim/v2/Users", json=payload, headers=_scim_headers(raw))
    user_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/scim/v2/Users/{user_id}",
        json={"active": False, "displayName": "Updated Name"},
        headers=_scim_headers(raw),
    )
    assert r.status_code == 200
    assert r.json()["active"] is False


# ── 6. Patch user ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scim_patch_user_deactivate(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    new_email = _email()
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": new_email,
        "emails": [{"value": new_email, "primary": True}],
        "active": True,
    }
    create_r = await client.post("/api/v1/scim/v2/Users", json=payload, headers=_scim_headers(raw))
    user_id = create_r.json()["id"]

    patch_payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{"op": "replace", "path": "active", "value": False}],
    }
    r = await client.patch(
        f"/api/v1/scim/v2/Users/{user_id}",
        json=patch_payload,
        headers=_scim_headers(raw),
    )
    assert r.status_code == 200
    assert r.json()["active"] is False


# ── 7. Delete (deprovision) user ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scim_delete_user(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    new_email = _email()
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": new_email,
        "emails": [{"value": new_email, "primary": True}],
        "active": True,
    }
    create_r = await client.post("/api/v1/scim/v2/Users", json=payload, headers=_scim_headers(raw))
    user_id = create_r.json()["id"]

    r = await client.delete(f"/api/v1/scim/v2/Users/{user_id}", headers=_scim_headers(raw))
    assert r.status_code == 204


# ── 8. SCIM filter ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scim_filter_by_username(client: AsyncClient, db_session: AsyncSession):
    _, tenant_id = await _register_user(client, db_session)
    raw = await _create_scim_token(db_session, tenant_id)

    new_email = _email()
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": new_email,
        "emails": [{"value": new_email, "primary": True}],
        "active": True,
    }
    await client.post("/api/v1/scim/v2/Users", json=payload, headers=_scim_headers(raw))

    r = await client.get(
        f'/api/v1/scim/v2/Users?filter=userName eq "{new_email}"',
        headers=_scim_headers(raw),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 1
    assert data["Resources"][0]["userName"] == new_email


# ── 9. Service Provider Config ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_provider_config(client: AsyncClient):
    r = await client.get("/api/v1/scim/v2/ServiceProviderConfig")
    assert r.status_code == 200
    data = r.json()
    assert "urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig" in data["schemas"]
    assert data["patch"]["supported"] is True
