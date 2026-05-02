"""Tests for the tenant-facing billing API."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant


def _email() -> str:
    return f"bill_{uuid.uuid4().hex[:8]}@test.com"


async def _register(client: AsyncClient) -> tuple[str, str]:
    email = _email()
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass1!", "full_name": "T"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["tenant_id"]


# ── GET /billing/usage ────────────────────────────────────────────────────────

async def test_billing_usage_default_values(client: AsyncClient):
    token, _ = await _register(client)
    r = await client.get("/api/v1/billing/usage", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["license_status"] == "trial"
    assert data["executions_used"] == 0
    assert data["executions_limit"] == 1000
    assert data["executions_pct"] == 0.0
    assert data["connectors_limit"] == 100


async def test_billing_usage_reflects_increments(
    client: AsyncClient, db_session: AsyncSession
):
    token, tenant_id = await _register(client)
    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
    )).scalar_one()
    tenant.executions_used = 850
    tenant.executions_limit = 1000
    tenant.license_status = "active"
    await db_session.commit()

    r = await client.get("/api/v1/billing/usage", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["executions_used"] == 850
    assert data["executions_pct"] == 85.0
    assert data["license_status"] == "active"


# ── GET /billing/license ──────────────────────────────────────────────────────

async def test_billing_license_returns_none_when_no_license(client: AsyncClient):
    token, _ = await _register(client)
    r = await client.get("/api/v1/billing/license", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() is None


# ── GET /billing/invoices — no Stripe key ─────────────────────────────────────

async def test_billing_invoices_empty_without_stripe(client: AsyncClient):
    token, _ = await _register(client)
    r = await client.get("/api/v1/billing/invoices", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


# ── POST /billing/stripe-webhook — invalid signature ─────────────────────────

async def test_stripe_webhook_invalid_signature(client: AsyncClient):
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.stripe_webhook_secret = "whsec_test"
        mock_settings.stripe_secret_key = "sk_test_x"

        with patch("stripe.Webhook.construct_event") as mock_event:
            import stripe as stripe_lib
            mock_event.side_effect = stripe_lib.error.SignatureVerificationError(
                "Invalid", "sig_header"
            )

            r = await client.post(
                "/api/v1/billing/stripe-webhook",
                content=b'{"type":"test"}',
                headers={"stripe-signature": "bad_sig", "Content-Type": "application/json"},
            )

    assert r.status_code == 400
    assert "Invalid webhook signature" in r.json()["detail"] or r.status_code == 400


# ── POST /billing/stripe-webhook — no secret configured → 400 ────────────────

async def test_stripe_webhook_no_secret_returns_400(client: AsyncClient):
    r = await client.post(
        "/api/v1/billing/stripe-webhook",
        content=b'{"type":"test"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


# ── trial_ends_at set on register ─────────────────────────────────────────────

async def test_trial_ends_at_set_on_registration(
    client: AsyncClient, db_session: AsyncSession
):
    token, tenant_id = await _register(client)
    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
    )).scalar_one()
    assert tenant.trial_ends_at is not None
    assert tenant.trial_ends_at > datetime.utcnow()


# ── contract_end days_remaining ───────────────────────────────────────────────

async def test_billing_usage_days_remaining(
    client: AsyncClient, db_session: AsyncSession
):
    token, tenant_id = await _register(client)
    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
    )).scalar_one()
    tenant.contract_end = datetime.utcnow() + timedelta(days=30)
    await db_session.commit()

    r = await client.get("/api/v1/billing/usage", headers={"Authorization": f"Bearer {token}"})
    data = r.json()
    assert data["days_remaining"] is not None
    assert 28 <= data["days_remaining"] <= 30
