import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TestSessionLocal


async def _register_and_login(client: AsyncClient, email: str, password: str = "Test1234!") -> str:
    await client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": "Test"
    })
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


async def _create_connector(client: AsyncClient, token: str, name: str = "C1") -> str:
    r = await client.post(
        "/api/v1/connectors",
        json={"name": name, "type": "rest", "base_url": "https://httpbin.org"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_create_pipeline_requires_two_steps(client: AsyncClient):
    token = await _register_and_login(client, "pl_min@test.com")
    cid = await _create_connector(client, token, "C1")

    r = await client.post(
        "/api/v1/pipelines",
        json={
            "name": "bad",
            "steps": [{"connector_id": cid, "step_order": 1, "name": "only"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_pipeline_success(client: AsyncClient):
    token = await _register_and_login(client, "pl_ok@test.com")
    cid1 = await _create_connector(client, token, "C1")
    cid2 = await _create_connector(client, token, "C2")

    r = await client.post(
        "/api/v1/pipelines",
        json={
            "name": "My Pipeline",
            "merge_strategy": "merge",
            "steps": [
                {"connector_id": cid1, "step_order": 1, "name": "Step 1"},
                {"connector_id": cid2, "step_order": 2, "name": "Step 2"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My Pipeline"
    assert len(data["steps"]) == 2
    assert data["executions_count"] == 0


@pytest.mark.asyncio
async def test_list_and_get_pipeline(client: AsyncClient):
    token = await _register_and_login(client, "pl_list@test.com")
    cid1 = await _create_connector(client, token, "C1")
    cid2 = await _create_connector(client, token, "C2")

    r = await client.post(
        "/api/v1/pipelines",
        json={
            "name": "Listed",
            "steps": [
                {"connector_id": cid1, "step_order": 1, "name": "S1"},
                {"connector_id": cid2, "step_order": 2, "name": "S2"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = r.json()["id"]

    r_list = await client.get("/api/v1/pipelines", headers={"Authorization": f"Bearer {token}"})
    assert r_list.status_code == 200
    assert any(p["id"] == pid for p in r_list.json())

    r_get = await client.get(f"/api/v1/pipelines/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert r_get.status_code == 200
    assert r_get.json()["id"] == pid


@pytest.mark.asyncio
async def test_update_pipeline(client: AsyncClient):
    token = await _register_and_login(client, "pl_upd@test.com")
    cid1 = await _create_connector(client, token, "C1")
    cid2 = await _create_connector(client, token, "C2")

    r = await client.post(
        "/api/v1/pipelines",
        json={
            "name": "Original",
            "steps": [
                {"connector_id": cid1, "step_order": 1, "name": "S1"},
                {"connector_id": cid2, "step_order": 2, "name": "S2"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = r.json()["id"]

    r_upd = await client.put(
        f"/api/v1/pipelines/{pid}",
        json={"name": "Updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_pipeline(client: AsyncClient):
    token = await _register_and_login(client, "pl_del@test.com")
    cid1 = await _create_connector(client, token, "C1")
    cid2 = await _create_connector(client, token, "C2")

    r = await client.post(
        "/api/v1/pipelines",
        json={
            "name": "ToDelete",
            "steps": [
                {"connector_id": cid1, "step_order": 1, "name": "S1"},
                {"connector_id": cid2, "step_order": 2, "name": "S2"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = r.json()["id"]

    r_del = await client.delete(f"/api/v1/pipelines/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert r_del.status_code == 204

    r_get = await client.get(f"/api/v1/pipelines/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert r_get.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_step_order_rejected(client: AsyncClient):
    token = await _register_and_login(client, "pl_dup@test.com")
    cid1 = await _create_connector(client, token, "C1")
    cid2 = await _create_connector(client, token, "C2")

    r = await client.post(
        "/api/v1/pipelines",
        json={
            "name": "bad",
            "steps": [
                {"connector_id": cid1, "step_order": 1, "name": "S1"},
                {"connector_id": cid2, "step_order": 1, "name": "S2"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_quota_counted_per_step_on_execute(client: AsyncClient):
    """Each step execution increments executions_used."""
    import uuid as _uuid
    from unittest.mock import AsyncMock, patch, MagicMock
    from sqlalchemy import select
    from app.models.tenant import Tenant

    token = await _register_and_login(client, "pl_quota@test.com")

    me_r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = _uuid.UUID(me_r.json()["tenant_id"])

    # Set large limit so no quota error
    async with TestSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
        tenant.executions_limit = 1000
        tenant.executions_used = 0
        tenant.license_status = "active"
        await db.commit()

    cid1 = await _create_connector(client, token, "QC1")
    cid2 = await _create_connector(client, token, "QC2")

    r = await client.post(
        "/api/v1/pipelines",
        json={
            "name": "QuotaPipeline",
            "steps": [
                {"connector_id": cid1, "step_order": 1, "name": "S1"},
                {"connector_id": cid2, "step_order": 2, "name": "S2"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    # Mock execute_connector to avoid real HTTP
    fake_exec = MagicMock()
    fake_exec.status = "success"
    fake_exec.response_payload = {"ok": True}
    fake_exec.error_message = None
    fake_exec.id = "00000000-0000-0000-0000-000000000001"

    # Create an API key
    r_key = await client.post(
        "/api/v1/api-keys",
        json={"name": "test-key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = r_key.json()["raw_key"]

    with patch("app.services.pipeline_engine.execute_connector", new=AsyncMock(return_value=fake_exec)):
        r_exec = await client.post(
            f"/api/v1/pipelines/{pid}/execute",
            json={"params": {}},
            headers={"X-API-Key": api_key},
        )

    assert r_exec.status_code == 200

    # executions_used should have been incremented twice (one per step)
    async with TestSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
        assert tenant.executions_used == 2
    # Remove local import aliases to avoid shadowing
    del _uuid
