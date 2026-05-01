"""Webhook dispatcher — unit and integration tests."""
import hashlib
import hmac
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.webhook_dispatcher import sign_payload


# ── A) Signature HMAC format et déterminisme ─────────────────────────────────

def test_sign_payload_format():
    secret = "my-test-secret-key-x"
    payload = {"event": "execution.success", "result": {"value": 42}}
    sig = sign_payload(secret, payload)

    assert sig.startswith("sha256=")
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    expected_hex = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert sig == f"sha256={expected_hex}"


def test_sign_payload_deterministic():
    """Same inputs always produce same signature regardless of dict key order."""
    secret = "stable-secret-key-1234"
    payload = {"z": 1, "a": 2, "m": 3}
    assert sign_payload(secret, payload) == sign_payload(secret, payload)


def test_sign_payload_different_secrets_produce_different_sigs():
    payload = {"event": "test"}
    assert sign_payload("secret-aaa-1234567", payload) != sign_payload("secret-bbb-1234567", payload)


# ── B) Dispatch filtre par événement ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_filters_by_event(client, db_session):
    """Only webhooks matching the execution event are enqueued."""
    from app.services import crypto, webhook_dispatcher
    from app.models.webhook_endpoint import WebhookEndpoint

    # Create user + connector via API
    tok_r = await client.post("/api/v1/auth/register", json={
        "email": "disp_ev@example.com", "password": "TestPass123!", "full_name": "Disp"
    })
    token = tok_r.json()["access_token"]
    con_r = await client.post(
        "/api/v1/connectors",
        json={"name": "DispConn", "type": "rest", "base_url": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    connector_id = uuid.UUID(con_r.json()["id"])
    tenant_id = uuid.UUID(con_r.json()["tenant_id"])

    enc = crypto.encrypt({"secret": "long-secret-key-for-dispatch-test"})
    wh_success = WebhookEndpoint(
        connector_id=connector_id, tenant_id=tenant_id,
        name="success hook", url="https://example.com/s",
        secret=enc, events=["execution.success"],
    )
    wh_failure = WebhookEndpoint(
        connector_id=connector_id, tenant_id=tenant_id,
        name="failure hook", url="https://example.com/f",
        secret=enc, events=["execution.failure"],
    )
    db_session.add(wh_success)
    db_session.add(wh_failure)
    await db_session.commit()

    dispatched: list[str] = []

    mock_task = MagicMock()
    mock_task.delay = lambda wid, payload, sig: dispatched.append(payload["event"])

    import app.workers.tasks as _tasks_mod
    with patch.object(_tasks_mod, "dispatch_webhook", mock_task):
        await webhook_dispatcher.dispatch(
            execution_id=uuid.uuid4(),
            connector_id=connector_id,
            connector_name="DispConn",
            tenant_id=tenant_id,
            triggered_by="manual",
            status="success",
            duration_ms=100,
            result={"data": 1},
            db=db_session,
        )

    assert dispatched == ["execution.success"]


# ── C) execution.all déclenche tous les webhooks ──────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_execution_all_triggers_any_status(client, db_session):
    from app.services import crypto, webhook_dispatcher
    from app.models.webhook_endpoint import WebhookEndpoint

    tok_r = await client.post("/api/v1/auth/register", json={
        "email": "disp_all@example.com", "password": "TestPass123!", "full_name": "All"
    })
    token = tok_r.json()["access_token"]
    con_r = await client.post(
        "/api/v1/connectors",
        json={"name": "AllConn", "type": "rest", "base_url": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    connector_id = uuid.UUID(con_r.json()["id"])
    tenant_id = uuid.UUID(con_r.json()["tenant_id"])

    enc = crypto.encrypt({"secret": "long-secret-key-for-dispatch-all-test"})
    wh_all = WebhookEndpoint(
        connector_id=connector_id, tenant_id=tenant_id,
        name="all hook", url="https://example.com/all",
        secret=enc, events=["execution.all"],
    )
    db_session.add(wh_all)
    await db_session.commit()

    dispatched: list[str] = []
    mock_task = MagicMock()
    mock_task.delay = lambda wid, payload, sig: dispatched.append(payload["event"])

    import app.workers.tasks as _tasks_mod
    with patch.object(_tasks_mod, "dispatch_webhook", mock_task):
        await webhook_dispatcher.dispatch(
            execution_id=uuid.uuid4(),
            connector_id=connector_id,
            connector_name="AllConn",
            tenant_id=tenant_id,
            triggered_by="scheduled",
            status="failure",
            duration_ms=50,
            result={},
            db=db_session,
        )

    assert dispatched == ["execution.failure"]


# ── D) Dispatch supprime toutes les exceptions ────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_suppresses_exceptions():
    """dispatch() must never raise even if the DB blows up."""
    from unittest.mock import AsyncMock
    from app.services import webhook_dispatcher

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=RuntimeError("DB boom"))

    # Should complete without raising
    await webhook_dispatcher.dispatch(
        execution_id=uuid.uuid4(),
        connector_id=uuid.uuid4(),
        connector_name="X",
        tenant_id=uuid.uuid4(),
        triggered_by="manual",
        status="success",
        duration_ms=50,
        result={},
        db=mock_db,
    )
