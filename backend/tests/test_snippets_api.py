"""Sprint SDK — /snippet endpoint API tests."""
import pytest
from httpx import AsyncClient


async def _setup(client: AsyncClient, tag: str) -> tuple[str, str]:
    """Register user and create a REST connector. Returns (token, connector_id)."""
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": f"snip_{tag}@example.com", "password": "TestPass123!", "full_name": "Snip User"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]

    rc = await client.post(
        "/api/v1/connectors",
        json={"name": "Mon Connecteur Test", "type": "rest", "base_url": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rc.status_code == 201
    return token, rc.json()["id"]


# ── A) Valid lang — curl ───────────────────────────────────────────────────────

async def test_snippet_curl(client: AsyncClient):
    token, cid = await _setup(client, "curl")
    r = await client.get(
        f"/api/v1/connectors/{cid}/snippet?lang=curl",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["lang"] == "curl"
    assert data["connector_id"] == cid
    assert "curl -X POST" in data["snippet"]
    assert cid in data["snippet"]


# ── B) All supported languages return 200 ─────────────────────────────────────

@pytest.mark.parametrize("lang", ["curl", "python", "javascript", "php", "java"])
async def test_snippet_all_langs(client: AsyncClient, lang: str):
    token, cid = await _setup(client, f"lang_{lang}")
    r = await client.get(
        f"/api/v1/connectors/{cid}/snippet?lang={lang}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["snippet"]


# ── C) Invalid lang → 422 ─────────────────────────────────────────────────────

async def test_snippet_invalid_lang(client: AsyncClient):
    token, cid = await _setup(client, "badlang")
    r = await client.get(
        f"/api/v1/connectors/{cid}/snippet?lang=ruby",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# ── D) Default lang is curl ────────────────────────────────────────────────────

async def test_snippet_default_lang(client: AsyncClient):
    token, cid = await _setup(client, "deflang")
    r = await client.get(
        f"/api/v1/connectors/{cid}/snippet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["lang"] == "curl"


# ── E) Tenant isolation ───────────────────────────────────────────────────────

async def test_snippet_tenant_isolation(client: AsyncClient):
    token1, cid1 = await _setup(client, "iso1_snip")

    r2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "snip_iso2@example.com", "password": "TestPass123!", "full_name": "Other"},
    )
    token2 = r2.json()["access_token"]

    r = await client.get(
        f"/api/v1/connectors/{cid1}/snippet?lang=curl",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r.status_code == 404


# ── F) api_key_id hint — valid key uses name in snippet ───────────────────────

async def test_snippet_with_api_key_id(client: AsyncClient):
    token, cid = await _setup(client, "keyid_snip")

    key_r = await client.post(
        "/api/v1/api-keys",
        json={"name": "Production Key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert key_r.status_code == 201
    key_id = key_r.json()["id"]

    r = await client.get(
        f"/api/v1/connectors/{cid}/snippet?lang=curl&api_key_id={key_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "bxc_production_key" in r.json()["snippet"]
    assert "YOUR_API_KEY" not in r.json()["snippet"]


# ── G) api_key_id from another tenant is silently ignored ─────────────────────

async def test_snippet_api_key_other_tenant_ignored(client: AsyncClient):
    token1, cid1 = await _setup(client, "keyiso_t1")

    r2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "snip_keyiso2@example.com", "password": "TestPass123!", "full_name": "T2"},
    )
    token2 = r2.json()["access_token"]

    key_r = await client.post(
        "/api/v1/api-keys",
        json={"name": "T2 Key"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    t2_key_id = key_r.json()["id"]

    r = await client.get(
        f"/api/v1/connectors/{cid1}/snippet?lang=curl&api_key_id={t2_key_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert r.status_code == 200
    assert "YOUR_API_KEY" in r.json()["snippet"]
