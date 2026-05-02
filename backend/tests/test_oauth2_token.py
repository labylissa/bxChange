"""Tests: POST /api/v1/oauth2/token (Client Credentials)."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth2_client import OAuth2Client
from passlib.context import CryptContext

_bcrypt = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def _register_and_login(client: AsyncClient) -> str:
    tag = uuid.uuid4().hex[:8]
    r = await client.post("/api/v1/auth/register", json={
        "email": f"oauth_{tag}@example.com",
        "password": "Pass123!",
        "full_name": "OAuth User",
    })
    return r.json()["access_token"]


async def _create_oauth2_client(
    client: AsyncClient, token: str, scopes: list[str] | None = None
) -> tuple[str, str]:
    """Returns (client_id, client_secret)."""
    r = await client.post(
        "/api/v1/oauth2-clients",
        json={
            "name": "Test Client",
            "scopes": scopes or ["execute:connectors"],
            "token_ttl_seconds": 3600,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return data["client_id"], data["client_secret"]


@pytest.mark.asyncio
async def test_token_valid(client: AsyncClient):
    token = await _register_and_login(client)
    cid, secret = await _create_oauth2_client(client, token)

    r = await client.post(
        "/api/v1/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": secret,
            "scope": "execute:connectors",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 3600
    assert "execute:connectors" in data["scope"]


@pytest.mark.asyncio
async def test_token_wrong_secret(client: AsyncClient):
    token = await _register_and_login(client)
    cid, _ = await _create_oauth2_client(client, token)

    r = await client.post(
        "/api/v1/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": "wrong_secret",
            "scope": "execute:connectors",
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_client"


@pytest.mark.asyncio
async def test_token_unknown_client(client: AsyncClient):
    r = await client.post(
        "/api/v1/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "bxc_client_doesnotexist",
            "client_secret": "whatever",
            "scope": "execute:connectors",
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_client"


@pytest.mark.asyncio
async def test_token_inactive_client(client: AsyncClient, db_session: AsyncSession):
    token = await _register_and_login(client)
    cid, secret = await _create_oauth2_client(client, token)

    # Deactivate via API
    list_r = await client.get("/api/v1/oauth2-clients", headers={"Authorization": f"Bearer {token}"})
    obj = next(c for c in list_r.json() if c["client_id"] == cid)
    await client.put(
        f"/api/v1/oauth2-clients/{obj['id']}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = await client.post(
        "/api/v1/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": secret,
            "scope": "execute:connectors",
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "client_inactive"


@pytest.mark.asyncio
async def test_token_scope_not_authorized(client: AsyncClient):
    token = await _register_and_login(client)
    cid, secret = await _create_oauth2_client(client, token, scopes=["execute:connectors"])

    r = await client.post(
        "/api/v1/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": secret,
            "scope": "execute:pipelines",  # not granted
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_scope"


@pytest.mark.asyncio
async def test_token_wrong_grant_type(client: AsyncClient):
    r = await client.post(
        "/api/v1/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": "bxc_client_x",
            "client_secret": "s",
            "scope": "execute:connectors",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "unsupported_grant_type"
