"""Sprint Scheduler — ScheduledJob API tests."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient


# ── Helpers ────────────────────────────────────────────────────────────────────

def _user(tag: str | None = None) -> dict:
    t = tag or uuid.uuid4().hex[:8]
    return {"email": f"sched_{t}@example.com", "password": "TestPass123!", "full_name": "Sched User"}


async def _register_and_token(client: AsyncClient, tag: str | None = None) -> str:
    r = await client.post("/api/v1/auth/register", json=_user(tag))
    assert r.status_code == 201
    return r.json()["access_token"]


async def _create_connector(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/api/v1/connectors",
        json={"name": "SchedTest", "type": "rest", "base_url": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    return r.json()["id"]


# ── A) Create cron job — valid ────────────────────────────────────────────────

async def test_create_cron_valid(client: AsyncClient):
    token = await _register_and_token(client, "cron_ok")
    cid = await _create_connector(client, token)

    r = await client.post(
        "/api/v1/scheduled-jobs",
        json={
            "connector_id": cid,
            "name": "Daily at noon",
            "schedule_type": "cron",
            "cron_expression": "0 12 * * *",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["schedule_type"] == "cron"
    assert data["cron_expression"] == "0 12 * * *"
    assert data["is_active"] is True
    assert data["next_run_at"] is not None
    assert data["connector_name"] == "SchedTest"


# ── B) Create cron job — invalid expression ───────────────────────────────────

async def test_create_cron_invalid_expression(client: AsyncClient):
    token = await _register_and_token(client, "cron_bad")
    cid = await _create_connector(client, token)

    r = await client.post(
        "/api/v1/scheduled-jobs",
        json={
            "connector_id": cid,
            "name": "Bad cron",
            "schedule_type": "cron",
            "cron_expression": "not a cron",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# ── C) Create interval — too short ─────────────────────────────────────────────

async def test_create_interval_too_short(client: AsyncClient):
    token = await _register_and_token(client, "interval_short")
    cid = await _create_connector(client, token)

    r = await client.post(
        "/api/v1/scheduled-jobs",
        json={
            "connector_id": cid,
            "name": "Too frequent",
            "schedule_type": "interval",
            "interval_seconds": 30,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# ── D) Create interval — valid ─────────────────────────────────────────────────

async def test_create_interval_valid(client: AsyncClient):
    token = await _register_and_token(client, "interval_ok")
    cid = await _create_connector(client, token)

    r = await client.post(
        "/api/v1/scheduled-jobs",
        json={
            "connector_id": cid,
            "name": "Every hour",
            "schedule_type": "interval",
            "interval_seconds": 3600,
            "input_params": {"key": "value"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["interval_seconds"] == 3600
    assert data["next_run_at"] is not None
    assert data["input_params"] == {"key": "value"}


# ── E) Toggle ─────────────────────────────────────────────────────────────────

async def test_toggle_scheduled_job(client: AsyncClient):
    token = await _register_and_token(client, "toggle")
    cid = await _create_connector(client, token)

    create_r = await client.post(
        "/api/v1/scheduled-jobs",
        json={"connector_id": cid, "name": "Toggle me", "schedule_type": "interval", "interval_seconds": 300},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = create_r.json()["id"]
    assert create_r.json()["is_active"] is True

    r = await client.post(
        f"/api/v1/scheduled-jobs/{job_id}/toggle",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    r2 = await client.post(
        f"/api/v1/scheduled-jobs/{job_id}/toggle",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.json()["is_active"] is True


# ── F) next_run_at is calculated correctly ─────────────────────────────────────

async def test_next_run_at_interval_is_in_future(client: AsyncClient):
    token = await _register_and_token(client, "next_run")
    cid = await _create_connector(client, token)

    before = datetime.utcnow()
    r = await client.post(
        "/api/v1/scheduled-jobs",
        json={"connector_id": cid, "name": "Next check", "schedule_type": "interval", "interval_seconds": 600},
        headers={"Authorization": f"Bearer {token}"},
    )
    after = datetime.utcnow()
    raw = r.json()["next_run_at"]
    next_run = datetime.fromisoformat(raw.replace("Z", "").rstrip("+00:00") if "+" in raw else raw)
    assert next_run > before
    diff = (next_run - after).total_seconds()
    assert 590 <= diff <= 610


# ── G) List filtered by connector_id ─────────────────────────────────────────

async def test_list_filtered_by_connector(client: AsyncClient):
    token = await _register_and_token(client, "list_filter")
    cid1 = await _create_connector(client, token)
    cid2 = await _create_connector(client, token)

    await client.post(
        "/api/v1/scheduled-jobs",
        json={"connector_id": cid1, "name": "Job A", "schedule_type": "interval", "interval_seconds": 300},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/api/v1/scheduled-jobs",
        json={"connector_id": cid2, "name": "Job B", "schedule_type": "interval", "interval_seconds": 300},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = await client.get(
        f"/api/v1/scheduled-jobs?connector_id={cid1}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    jobs = r.json()
    assert all(j["connector_id"] == cid1 for j in jobs)


# ── H) Delete ─────────────────────────────────────────────────────────────────

async def test_delete_scheduled_job(client: AsyncClient):
    token = await _register_and_token(client, "delete")
    cid = await _create_connector(client, token)

    create_r = await client.post(
        "/api/v1/scheduled-jobs",
        json={"connector_id": cid, "name": "To delete", "schedule_type": "interval", "interval_seconds": 300},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = create_r.json()["id"]

    r = await client.delete(f"/api/v1/scheduled-jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204

    r2 = await client.get(f"/api/v1/scheduled-jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 404
