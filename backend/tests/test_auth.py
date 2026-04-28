import uuid

import pytest
from httpx import AsyncClient


def _user(suffix: str | None = None) -> dict:
    tag = suffix or uuid.uuid4().hex[:8]
    return {
        "email": f"user_{tag}@example.com",
        "password": "SecurePass123!",
        "full_name": "Test User",
    }


async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_register(client: AsyncClient):
    r = await client.post("/api/v1/auth/register", json=_user())
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_register_duplicate_email(client: AsyncClient):
    payload = _user("dup")
    await client.post("/api/v1/auth/register", json=payload)
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409


async def test_login_success(client: AsyncClient):
    u = _user()
    await client.post("/api/v1/auth/register", json=u)
    r = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": u["password"]})
    assert r.status_code == 200
    assert "access_token" in r.json()


async def test_login_wrong_password(client: AsyncClient):
    u = _user()
    await client.post("/api/v1/auth/register", json=u)
    r = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": "wrong!"})
    assert r.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@nowhere.com", "password": "x"},
    )
    assert r.status_code == 401


async def test_me_authenticated(client: AsyncClient):
    u = _user()
    reg = await client.post("/api/v1/auth/register", json=u)
    token = reg.json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == u["email"]
    assert r.json()["role"] == "admin"


async def test_me_no_token(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")
    # HTTPBearer returns 401/403 when Authorization header is absent
    assert r.status_code in (401, 403)


async def test_me_invalid_token(client: AsyncClient):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


async def test_token_refresh(client: AsyncClient):
    reg = await client.post("/api/v1/auth/register", json=_user())
    refresh_token = reg.json()["refresh_token"]
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_refresh_token_rotation(client: AsyncClient):
    """Using the same refresh token twice must fail on the second use."""
    reg = await client.post("/api/v1/auth/register", json=_user())
    refresh_token = reg.json()["refresh_token"]
    await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 401


async def test_logout_invalidates_refresh_token(client: AsyncClient):
    reg = await client.post("/api/v1/auth/register", json=_user())
    tokens = reg.json()
    await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_access_token_used_as_refresh_rejected(client: AsyncClient):
    reg = await client.post("/api/v1/auth/register", json=_user())
    access_token = reg.json()["access_token"]
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert r.status_code == 401
