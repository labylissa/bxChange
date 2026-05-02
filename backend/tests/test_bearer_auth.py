"""Tests: Bearer OAuth2 token on /execute endpoints."""
import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import settings


async def _register_and_login(client: AsyncClient) -> str:
    tag = uuid.uuid4().hex[:8]
    r = await client.post("/api/v1/auth/register", json={
        "email": f"bearer_{tag}@example.com",
        "password": "Pass123!",
        "full_name": "Bearer User",
    })
    return r.json()["access_token"]


async def _create_oauth2_client(client: AsyncClient, token: str) -> tuple[str, str]:
    r = await client.post(
        "/api/v1/oauth2-clients",
        json={"name": "Bearer Test", "scopes": ["execute:connectors", "execute:pipelines"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = r.json()
    return data["client_id"], data["client_secret"]


async def _get_oauth2_bearer(client: AsyncClient, cid: str, secret: str) -> str:
    r = await client.post(
        "/api/v1/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": secret,
            "scope": "execute:connectors execute:pipelines",
        },
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _make_expired_token(tenant_id: str) -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "scopes": ["execute:connectors"],
        "type": "oauth2_client",
        "exp": datetime.utcnow() - timedelta(hours=1),
        "iat": datetime.utcnow() - timedelta(hours=2),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


@pytest.mark.asyncio
async def test_oauth2_bearer_accepted_on_execute(client: AsyncClient):
    """OAuth2 Bearer token must be accepted where X-API-Key is accepted."""
    user_token = await _register_and_login(client)
    cid, secret = await _create_oauth2_client(client, user_token)
    bearer = await _get_oauth2_bearer(client, cid, secret)

    # We don't have a real connector to execute — just verify auth is accepted (404 = connector not found, not 401)
    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/connectors/{fake_id}/execute",
        json={"params": {}},
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert r.status_code != 401, f"Expected auth accepted, got 401: {r.text}"


@pytest.mark.asyncio
async def test_expired_oauth2_bearer_rejected(client: AsyncClient):
    user_token = await _register_and_login(client)
    tag = uuid.uuid4().hex[:8]
    # Get any tenant_id by checking the user's tenant via /auth/me
    me_r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    tenant_id = me_r.json().get("tenant_id", str(uuid.uuid4()))

    expired = _make_expired_token(tenant_id)
    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/connectors/{fake_id}/execute",
        json={"params": {}},
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_malformed_bearer_rejected(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/connectors/{fake_id}/execute",
        json={"params": {}},
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_user_bearer_still_accepted(client: AsyncClient):
    """Regular user session Bearer must still work (regression guard)."""
    user_token = await _register_and_login(client)
    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/connectors/{fake_id}/execute",
        json={"params": {}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    # Should be 404 (connector not found) not 401
    assert r.status_code != 401, f"User Bearer rejected: {r.text}"


@pytest.mark.asyncio
async def test_api_key_still_accepted(client: AsyncClient):
    """X-API-Key must still work (regression guard)."""
    user_token = await _register_and_login(client)
    # Create API key
    key_r = await client.post(
        "/api/v1/api-keys",
        json={"name": "test-key"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert key_r.status_code == 201
    raw_key = key_r.json()["raw_key"]

    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/connectors/{fake_id}/execute",
        json={"params": {}},
        headers={"X-API-Key": raw_key},
    )
    assert r.status_code != 401, f"X-API-Key rejected: {r.text}"
