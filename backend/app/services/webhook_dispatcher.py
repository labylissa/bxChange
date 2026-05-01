"""Webhook dispatcher — best-effort, non-blocking delivery via Celery tasks."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_log = logging.getLogger(__name__)


def sign_payload(secret: str, payload: dict) -> str:
    """Compute HMAC-SHA256 signature over deterministically serialised payload."""
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def dispatch(
    *,
    execution_id: uuid.UUID,
    connector_id: uuid.UUID,
    connector_name: str,
    tenant_id: uuid.UUID,
    triggered_by: str,
    status: str,
    duration_ms: int | None,
    result: dict,
    db: AsyncSession,
) -> None:
    """Enqueue one Celery task per matching active webhook endpoint. Never raises."""
    try:
        from app.models.webhook_endpoint import WebhookEndpoint
        from app.services import crypto
        from app.workers.tasks import dispatch_webhook

        event = f"execution.{status}"
        payload = {
            "event": event,
            "connector_id": str(connector_id),
            "connector_name": connector_name,
            "tenant_id": str(tenant_id),
            "triggered_by": triggered_by,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "execution_id": str(execution_id),
            "duration_ms": duration_ms,
            "result": result,
        }

        webhooks = (await db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.connector_id == connector_id,
                WebhookEndpoint.is_active.is_(True),
            )
        )).scalars().all()

        for wh in webhooks:
            if event not in wh.events and "execution.all" not in wh.events:
                continue
            try:
                secret = crypto.decrypt(wh.secret)["secret"]
                sig = sign_payload(secret, payload)
                dispatch_webhook.delay(str(wh.id), payload, sig)
            except Exception:
                _log.exception("Failed to enqueue webhook %s", wh.id)

    except Exception:
        _log.exception("webhook_dispatcher.dispatch failed — suppressed")
