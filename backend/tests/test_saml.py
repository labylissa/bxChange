"""Sprint 18 — SAML / SSO tests."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scim_token import ScimToken
from app.models.sso_config import SSOConfig
from app.models.sso_domain_hint import SSODomainHint
from app.models.user import User
from app.services import crypto


# ── Helpers ───────────────────────────────────────────────────────────────────

def _email() -> str:
    return f"{uuid.uuid4().hex[:8]}@example.com"


async def _register_and_login(client: AsyncClient, role: str = "admin") -> tuple[str, str]:
    """Register a user, return (access_token, email)."""
    email = _email()
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass1!", "full_name": "Test"},
    )
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass1!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], email


async def _make_admin(db: AsyncSession, email: str) -> None:
    """Elevate a user to admin role."""
    from sqlalchemy import select, update
    await db.execute(
        __import__("sqlalchemy", fromlist=["update"]).update(User)
        .where(User.email == email)
        .values(role="admin")
    )
    await db.commit()


def _sso_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── 1. SSO Config CRUD ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_sso_config(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    r = await client.post(
        "/api/v1/sso/config",
        json={
            "idp_type": "saml",
            "entity_id": "https://idp.example.com/saml",
            "sso_url": "https://idp.example.com/sso",
            "certificate": "MIIFAKE...",
            "domains": ["example.com"],
        },
        headers=_sso_headers(token),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["idp_type"] == "saml"
    assert data["entity_id"] == "https://idp.example.com/saml"
    # Certificate is never returned
    assert "certificate" not in data


@pytest.mark.asyncio
async def test_create_sso_config_duplicate_returns_409(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    payload = {
        "idp_type": "saml",
        "entity_id": f"https://idp-{uuid.uuid4().hex[:6]}.com/saml",
        "sso_url": "https://idp.example.com/sso",
        "domains": [],
    }
    r1 = await client.post("/api/v1/sso/config", json=payload, headers=_sso_headers(token))
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/sso/config", json=payload, headers=_sso_headers(token))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_get_sso_config(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    await client.post(
        "/api/v1/sso/config",
        json={
            "idp_type": "oidc",
            "entity_id": "client-id-123",
            "sso_url": "https://accounts.google.com",
            "domains": [],
        },
        headers=_sso_headers(token),
    )
    r = await client.get("/api/v1/sso/config", headers=_sso_headers(token))
    assert r.status_code == 200
    assert r.json()["idp_type"] == "oidc"


@pytest.mark.asyncio
async def test_get_sso_config_404_when_none(client: AsyncClient, db_session: AsyncSession):
    token, _ = await _register_and_login(client)
    await _make_admin(db_session, _)
    r = await client.get("/api/v1/sso/config", headers=_sso_headers(token))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_sso_config(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    await client.post(
        "/api/v1/sso/config",
        json={
            "idp_type": "saml",
            "entity_id": "old-entity",
            "sso_url": "https://old.idp.com",
            "domains": [],
        },
        headers=_sso_headers(token),
    )
    r = await client.put(
        "/api/v1/sso/config",
        json={"entity_id": "new-entity", "is_active": False},
        headers=_sso_headers(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == "new-entity"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_delete_sso_config(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    await client.post(
        "/api/v1/sso/config",
        json={
            "idp_type": "saml",
            "entity_id": f"entity-{uuid.uuid4().hex}",
            "sso_url": "https://idp.example.com",
            "domains": [],
        },
        headers=_sso_headers(token),
    )
    r = await client.delete("/api/v1/sso/config", headers=_sso_headers(token))
    assert r.status_code == 204

    r2 = await client.get("/api/v1/sso/config", headers=_sso_headers(token))
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_sso_config_requires_admin(client: AsyncClient, db_session: AsyncSession):
    # Register returns admin; downgrade to viewer to test guard
    token, email = await _register_and_login(client)
    from sqlalchemy import update
    await db_session.execute(update(User).where(User.email == email).values(role="viewer"))
    await db_session.commit()

    r = await client.post(
        "/api/v1/sso/config",
        json={"idp_type": "saml", "entity_id": "x", "sso_url": "https://x.com", "domains": []},
        headers=_sso_headers(token),
    )
    assert r.status_code == 403


# ── 2. Domain Hint ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_domain_hint_found(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    domain = f"{uuid.uuid4().hex[:6]}.io"
    await client.post(
        "/api/v1/sso/config",
        json={
            "idp_type": "saml",
            "entity_id": f"https://idp-{uuid.uuid4().hex}.com",
            "sso_url": "https://idp.example.com",
            "domains": [domain],
        },
        headers=_sso_headers(token),
    )
    r = await client.get(f"/api/v1/sso/domain-hint/{domain}")
    assert r.status_code == 200
    assert r.json()["domain"] == domain


@pytest.mark.asyncio
async def test_domain_hint_not_found(client: AsyncClient):
    r = await client.get("/api/v1/sso/domain-hint/notregistered.example")
    assert r.status_code == 404


# ── 3. SCIM Token CRUD ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_scim_token(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    r = await client.post(
        "/api/v1/sso/scim-tokens",
        json={"name": "Azure AD provisioning"},
        headers=_sso_headers(token),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert "raw_token" in data
    assert data["name"] == "Azure AD provisioning"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_raw_token_not_in_list(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    await client.post(
        "/api/v1/sso/scim-tokens",
        json={"name": "Okta"},
        headers=_sso_headers(token),
    )
    r = await client.get("/api/v1/sso/scim-tokens", headers=_sso_headers(token))
    assert r.status_code == 200
    for item in r.json():
        assert "raw_token" not in item


@pytest.mark.asyncio
async def test_revoke_scim_token(client: AsyncClient, db_session: AsyncSession):
    token, email = await _register_and_login(client)
    await _make_admin(db_session, email)

    create_r = await client.post(
        "/api/v1/sso/scim-tokens",
        json={"name": "To revoke"},
        headers=_sso_headers(token),
    )
    token_id = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/sso/scim-tokens/{token_id}",
        headers=_sso_headers(token),
    )
    assert r.status_code == 204


# ── 4. JIT Provisioning ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jit_provision_creates_user(db_session: AsyncSession):
    """jit_provision creates a new user from SAML attrs."""
    from app.services.saml_service import jit_provision

    tenant_id = uuid.uuid4()

    sso_config = MagicMock()
    sso_config.attr_mapping = {
        "role_mapping": {"Admins": "admin", "Devs": "developer"}
    }

    attrs = {"email": f"{uuid.uuid4().hex[:6]}@jit-test.com", "name": "JIT User", "groups": ["Devs"]}
    user = await jit_provision(db_session, tenant_id, sso_config, attrs)

    assert user.email == attrs["email"]
    assert user.role == "developer"
    assert user.tenant_id == tenant_id


@pytest.mark.asyncio
async def test_jit_provision_updates_existing_user(db_session: AsyncSession):
    """jit_provision updates role when it changes."""
    from app.services.saml_service import jit_provision

    email = f"{uuid.uuid4().hex[:6]}@jit-update.com"
    tenant_id = uuid.uuid4()

    existing = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="!sso:x",
        full_name="Old Name",
        tenant_id=tenant_id,
        role="viewer",
        is_active=True,
    )
    db_session.add(existing)
    await db_session.commit()

    sso_config = MagicMock()
    sso_config.attr_mapping = {"role_mapping": {"Admins": "admin"}}

    attrs = {"email": email, "name": "New Name", "groups": ["Admins"]}
    user = await jit_provision(db_session, tenant_id, sso_config, attrs)

    assert user.role == "admin"
    assert user.full_name == "New Name"


@pytest.mark.asyncio
async def test_jit_provision_missing_email_raises(db_session: AsyncSession):
    """jit_provision raises 400 when email is empty."""
    from fastapi import HTTPException
    from app.services.saml_service import jit_provision

    sso_config = MagicMock()
    sso_config.attr_mapping = {}

    with pytest.raises(HTTPException) as exc_info:
        await jit_provision(db_session, uuid.uuid4(), sso_config, {"email": "", "name": "", "groups": []})
    assert exc_info.value.status_code == 400


# ── 5. SAML process_acs — mocked ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_acs_valid(db_session: AsyncSession):
    """process_acs returns attrs when SAML is valid."""
    from app.services.saml_service import process_acs

    sso_config = MagicMock()
    sso_config.entity_id = "https://idp.example.com"
    sso_config.sso_url = "https://idp.example.com/sso"
    sso_config.certificate = None
    sso_config.attr_mapping = {"email_attr": "email", "name_attr": "name"}

    mock_auth_instance = MagicMock()
    mock_auth_instance.get_errors.return_value = []
    mock_auth_instance.is_authenticated.return_value = True
    mock_auth_instance.get_attributes.return_value = {"email": ["alice@example.com"], "name": ["Alice"]}
    mock_auth_instance.get_nameid.return_value = "alice@example.com"
    mock_auth_class = MagicMock(return_value=mock_auth_instance)

    with patch("app.services.saml_service._get_saml_auth", return_value=mock_auth_class):
        attrs = process_acs(sso_config, "fake-saml-response", "relay")

    assert attrs["email"] == "alice@example.com"
    assert attrs["name"] == "Alice"


@pytest.mark.asyncio
async def test_process_acs_invalid_raises(db_session: AsyncSession):
    """process_acs raises 401 on SAML errors."""
    from fastapi import HTTPException
    from app.services.saml_service import process_acs

    sso_config = MagicMock()
    sso_config.certificate = None
    sso_config.attr_mapping = {}

    mock_auth_instance = MagicMock()
    mock_auth_instance.get_errors.return_value = ["invalid_response"]
    mock_auth_instance.is_authenticated.return_value = False
    mock_auth_class = MagicMock(return_value=mock_auth_instance)

    with patch("app.services.saml_service._get_saml_auth", return_value=mock_auth_class):
        with pytest.raises(HTTPException) as exc_info:
            process_acs(sso_config, "bad-saml", "relay")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_process_acs_not_authenticated_raises(db_session: AsyncSession):
    """process_acs raises 401 when is_authenticated is False even with no errors."""
    from fastapi import HTTPException
    from app.services.saml_service import process_acs

    sso_config = MagicMock()
    sso_config.certificate = None
    sso_config.attr_mapping = {}

    mock_auth_instance = MagicMock()
    mock_auth_instance.get_errors.return_value = []
    mock_auth_instance.is_authenticated.return_value = False
    mock_auth_class = MagicMock(return_value=mock_auth_instance)

    with patch("app.services.saml_service._get_saml_auth", return_value=mock_auth_class):
        with pytest.raises(HTTPException) as exc_info:
            process_acs(sso_config, "bad-saml", "relay")

    assert exc_info.value.status_code == 401
