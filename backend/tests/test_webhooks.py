"""Sprint Webhooks — API tests."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ── Helpers ────────────────────────────────────────────────────────────────────

def _user(tag: str) -> dict:
    return {"email": f"wh_{tag}@example.com", "password": "TestPass123!", "full_name": "WH User"}


async def _register_and_token(client: AsyncClient, tag: str) -> str:
    r = await client.post("/api/v1/auth/register", json=_user(tag))
    assert r.status_code == 201
    return r.json()["access_token"]


async def _create_connector(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/api/v1/connectors",
        json={"name": "WHTest", "type": "rest", "base_url": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    return r.json()["id"]


_WH_PAYLOAD = {
    "name": "My Webhook",
    "url": "https://example.com/hook",
    "secret": "supersecretkey12345",
    "events": ["execution.success"],
}


# ── A) URL non-HTTPS rejeté ────────────────────────────────────────────────────

async def test_create_webhook_http_url_rejected(client: AsyncClient):
    token = await _register_and_token(client, "http_reject")
    cid = await _create_connector(client, token)

    r = await client.post(
        "/api/v1/webhooks",
        json={**_WH_PAYLOAD, "connector_id": cid, "url": "http://example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# ── B) Secret trop court rejeté ───────────────────────────────────────────────

async def test_create_webhook_short_secret_rejected(client: AsyncClient):
    token = await _register_and_token(client, "short_secret")
    cid = await _create_connector(client, token)

    r = await client.post(
        "/api/v1/webhooks",
        json={**_WH_PAYLOAD, "connector_id": cid, "secret": "tooshort"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# ── C) Événement invalide rejeté ──────────────────────────────────────────────

async def test_create_webhook_invalid_event_rejected(client: AsyncClient):
    token = await _register_and_token(client, "bad_event")
    cid = await _create_connector(client, token)

    r = await client.post(
        "/api/v1/webhooks",
        json={**_WH_PAYLOAD, "connector_id": cid, "events": ["execution.unknown"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# ── D) Création valide ────────────────────────────────────────────────────────

async def test_create_webhook_valid(client: AsyncClient):
    token = await _register_and_token(client, "create_ok")
    cid = await _create_connector(client, token)

    r = await client.post(
        "/api/v1/webhooks",
        json={**_WH_PAYLOAD, "connector_id": cid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["url"] == "https://example.com/hook"
    assert "secret" not in data  # secret never returned
    assert data["is_active"] is True
    assert data["events"] == ["execution.success"]


# ── E) Toggle ─────────────────────────────────────────────────────────────────

async def test_toggle_webhook(client: AsyncClient):
    token = await _register_and_token(client, "toggle_wh")
    cid = await _create_connector(client, token)

    create_r = await client.post(
        "/api/v1/webhooks",
        json={**_WH_PAYLOAD, "connector_id": cid},
        headers={"Authorization": f"Bearer {token}"},
    )
    wh_id = create_r.json()["id"]
    assert create_r.json()["is_active"] is True

    r = await client.post(f"/api/v1/webhooks/{wh_id}/toggle", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    r2 = await client.post(f"/api/v1/webhooks/{wh_id}/toggle", headers={"Authorization": f"Bearer {token}"})
    assert r2.json()["is_active"] is True


# ── F) Endpoint /test avec httpx mocké ───────────────────────────────────────

async def test_test_endpoint_success(client: AsyncClient):
    token = await _register_and_token(client, "test_ep")
    cid = await _create_connector(client, token)

    create_r = await client.post(
        "/api/v1/webhooks",
        json={**_WH_PAYLOAD, "connector_id": cid},
        headers={"Authorization": f"Bearer {token}"},
    )
    wh_id = create_r.json()["id"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock(post=AsyncMock(return_value=mock_resp)))
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.webhooks.httpx.AsyncClient", return_value=mock_cm):
        r = await client.post(f"/api/v1/webhooks/{wh_id}/test", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["status_code"] == 200


# ── G) Liste filtrée par connector_id ─────────────────────────────────────────

async def test_list_filtered_by_connector(client: AsyncClient):
    token = await _register_and_token(client, "list_filter_wh")
    cid1 = await _create_connector(client, token)
    cid2 = await _create_connector(client, token)

    await client.post("/api/v1/webhooks", json={**_WH_PAYLOAD, "connector_id": cid1}, headers={"Authorization": f"Bearer {token}"})
    await client.post("/api/v1/webhooks", json={**_WH_PAYLOAD, "connector_id": cid2, "name": "WH2"}, headers={"Authorization": f"Bearer {token}"})

    r = await client.get(f"/api/v1/webhooks?connector_id={cid1}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert all(w["connector_id"] == cid1 for w in r.json())


# ── H) Suppression ────────────────────────────────────────────────────────────

async def test_delete_webhook(client: AsyncClient):
    token = await _register_and_token(client, "delete_wh")
    cid = await _create_connector(client, token)

    create_r = await client.post(
        "/api/v1/webhooks",
        json={**_WH_PAYLOAD, "connector_id": cid},
        headers={"Authorization": f"Bearer {token}"},
    )
    wh_id = create_r.json()["id"]

    r = await client.delete(f"/api/v1/webhooks/{wh_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204

    r2 = await client.get(f"/api/v1/webhooks/{wh_id}", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 404
