"""Sprint 8 — API Keys tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.services import api_key_service


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


async def _create_key(client: AsyncClient, token: str, **kwargs) -> dict:
    payload = {"name": "test-key", **kwargs}
    r = await client.post(
        "/api/v1/api-keys",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _connector(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/api/v1/connectors",
        json={"name": f"C-{uuid.uuid4().hex[:6]}", "type": "rest", "base_url": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── 1. Création — raw_key retourné une seule fois ─────────────────────────────

async def test_create_returns_raw_key(client: AsyncClient):
    token = await _auth(client)
    data = await _create_key(client, token)

    assert "raw_key" in data
    assert data["raw_key"]
    assert "key_hash" not in data
    assert "id" in data
    assert data["is_active"] is True


# ── 2. raw_key commence par "bxc_" ────────────────────────────────────────────

async def test_raw_key_prefix(client: AsyncClient):
    token = await _auth(client)
    data = await _create_key(client, token)
    assert data["raw_key"].startswith("bxc_")


# ── 3. key_hash jamais exposé dans les réponses ───────────────────────────────

async def test_key_hash_never_exposed(client: AsyncClient):
    token = await _auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    await _create_key(client, token)

    # Check creation response — already tested above
    # Check list response
    r = await client.get("/api/v1/api-keys", headers=headers)
    assert r.status_code == 200
    for item in r.json():
        assert "key_hash" not in item
        assert "raw_key" not in item


# ── 4. Validation clé valide → ApiKey retourné ───────────────────────────────

async def test_validate_valid_key(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    data = await _create_key(client, token)
    raw_key = data["raw_key"]

    result = await api_key_service.validate_api_key(raw_key, db_session)
    assert result is not None
    assert str(result.id) == data["id"]
    assert result.is_active is True


# ── 5. Validation clé invalide → None ────────────────────────────────────────

async def test_validate_invalid_key(client: AsyncClient, db_session: AsyncSession):
    result = await api_key_service.validate_api_key("bxc_totally_fake_key_xyz", db_session)
    assert result is None


# ── 6. Validation clé révoquée → None ────────────────────────────────────────

async def test_validate_revoked_key(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    data = await _create_key(client, token)
    raw_key = data["raw_key"]
    key_id = data["id"]

    # Revoke
    r = await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert r.status_code == 204

    result = await api_key_service.validate_api_key(raw_key, db_session)
    assert result is None


# ── 7. Validation clé expirée → None ─────────────────────────────────────────

async def test_validate_expired_key(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    # Create key that expired 1 hour ago
    past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    data = await _create_key(client, token, expires_at=past)
    raw_key = data["raw_key"]

    result = await api_key_service.validate_api_key(raw_key, db_session)
    assert result is None


# ── 8. Rate limit: 5 appels ok, 6e → False ───────────────────────────────────

async def test_rate_limit_service(client: AsyncClient, db_session: AsyncSession, fake_redis):
    token = await _auth(client)
    data = await _create_key(client, token, rate_limit=5)
    raw_key = data["raw_key"]

    api_key = await api_key_service.validate_api_key(raw_key, db_session)
    assert api_key is not None

    for i in range(5):
        ok = await api_key_service.check_rate_limit(api_key, fake_redis)
        assert ok is True, f"Call {i+1} should be within limit"

    over = await api_key_service.check_rate_limit(api_key, fake_redis)
    assert over is False


# ── 9. /execute avec X-API-Key valide → 200 ──────────────────────────────────

async def test_execute_with_valid_api_key(client: AsyncClient):
    token = await _auth(client)
    cid = await _connector(client, token)
    data = await _create_key(client, token)
    raw_key = data["raw_key"]

    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        return_value={"status_code": 200, "headers": {}, "body": {"ok": True}},
    ):
        r = await client.post(
            f"/api/v1/connectors/{cid}/execute",
            json={"params": {}},
            headers={"X-API-Key": raw_key},
        )

    assert r.status_code == 200
    assert r.json()["status"] == "success"


# ── 10. /execute avec X-API-Key invalide → 401 ───────────────────────────────

async def test_execute_with_invalid_api_key(client: AsyncClient):
    token = await _auth(client)
    cid = await _connector(client, token)

    r = await client.post(
        f"/api/v1/connectors/{cid}/execute",
        json={"params": {}},
        headers={"X-API-Key": "bxc_this_key_does_not_exist"},
    )
    assert r.status_code == 401


# ── 11. /execute avec rate limit dépassé → 429 ───────────────────────────────

async def test_execute_rate_limit_exceeded(client: AsyncClient):
    token = await _auth(client)
    cid = await _connector(client, token)
    data = await _create_key(client, token, rate_limit=2)
    raw_key = data["raw_key"]
    api_headers = {"X-API-Key": raw_key}

    mock_resp = {"status_code": 200, "headers": {}, "body": {}}
    with patch(
        "app.services.execution_service.rest_engine.execute",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        r1 = await client.post(
            f"/api/v1/connectors/{cid}/execute", json={"params": {}}, headers=api_headers
        )
        r2 = await client.post(
            f"/api/v1/connectors/{cid}/execute", json={"params": {}}, headers=api_headers
        )
        r3 = await client.post(
            f"/api/v1/connectors/{cid}/execute", json={"params": {}}, headers=api_headers
        )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


# ── 12. DELETE révoque sans supprimer la ligne ────────────────────────────────

async def test_delete_revokes_not_deletes(client: AsyncClient, db_session: AsyncSession):
    token = await _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    data = await _create_key(client, token)
    key_id = uuid.UUID(data["id"])

    r = await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert r.status_code == 204

    # Row must still exist in the DB
    result = await db_session.execute(select(ApiKey).where(ApiKey.id == key_id))
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.is_active is False


# ── 13. Isolation tenant sur liste des clés ───────────────────────────────────

async def test_tenant_isolation_list(client: AsyncClient):
    token1 = await _auth(client)
    token2 = await _auth(client)

    # Tenant 1 creates 2 keys, tenant 2 creates 1 key
    await _create_key(client, token1, name="key-a")
    await _create_key(client, token1, name="key-b")
    await _create_key(client, token2, name="key-c")

    r1 = await client.get(
        "/api/v1/api-keys", headers={"Authorization": f"Bearer {token1}"}
    )
    r2 = await client.get(
        "/api/v1/api-keys", headers={"Authorization": f"Bearer {token2}"}
    )

    assert r1.status_code == 200
    assert r2.status_code == 200

    names1 = {k["name"] for k in r1.json()}
    names2 = {k["name"] for k in r2.json()}

    assert "key-a" in names1
    assert "key-b" in names1
    assert "key-c" not in names1
    assert "key-c" in names2
    assert "key-a" not in names2
