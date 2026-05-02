"""Billing API — tenant-facing usage, invoices, and Stripe webhook."""
from __future__ import annotations

import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.models.license import License
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.license import BillingUsage, InvoiceResponse, LicenseRead

router = APIRouter(prefix="/billing", tags=["billing"])
_log = logging.getLogger(__name__)

_401 = {"description": "Token invalide ou expiré"}


def _configure_stripe() -> None:
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key


def _days_remaining(contract_end: datetime | None) -> int | None:
    if contract_end is None:
        return None
    return max(0, (contract_end - datetime.utcnow()).days)


# ── GET /billing/license ───────────────────────────────────────────────────────

@router.get(
    "/license",
    response_model=LicenseRead | None,
    summary="Licence courante du tenant",
    responses={200: {"description": "Licence active ou null"}, 401: _401},
)
async def get_current_license(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LicenseRead | None:
    lic = (await db.execute(
        select(License)
        .where(License.tenant_id == current_user.tenant_id)
        .order_by(License.created_at.desc())
    )).scalars().first()
    return LicenseRead.model_validate(lic) if lic else None


# ── GET /billing/usage ─────────────────────────────────────────────────────────

@router.get(
    "/usage",
    response_model=BillingUsage,
    summary="Quota et usage du mois",
    responses={200: {"description": "Usage"}, 401: _401},
)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingUsage:
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    pct = (
        tenant.executions_used / tenant.executions_limit * 100
        if tenant.executions_limit > 0
        else 0.0
    )
    return BillingUsage(
        license_status=tenant.license_status,
        executions_used=tenant.executions_used,
        executions_limit=tenant.executions_limit,
        executions_pct=round(pct, 1),
        connectors_used=tenant.connectors_count,
        connectors_limit=tenant.connectors_limit,
        contract_end=tenant.contract_end,
        days_remaining=_days_remaining(tenant.contract_end),
        trial_ends_at=tenant.trial_ends_at,
    )


# ── GET /billing/invoices ──────────────────────────────────────────────────────

@router.get(
    "/invoices",
    summary="Factures Stripe du tenant",
    responses={200: {"description": "Liste des factures"}, 401: _401},
)
async def list_invoices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    _configure_stripe()
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )).scalar_one_or_none()

    if not tenant or not tenant.stripe_customer_id or not settings.stripe_secret_key:
        return []

    try:
        invoices = stripe.Invoice.list(customer=tenant.stripe_customer_id, limit=20)
        return [
            {
                "invoice_id": inv.id,
                "date": datetime.fromtimestamp(inv.created).isoformat(),
                "description": inv.description or "",
                "amount_cents": inv.amount_due,
                "currency": inv.currency,
                "status": inv.status,
                "invoice_url": inv.get("hosted_invoice_url"),
                "pdf_url": inv.get("invoice_pdf"),
            }
            for inv in invoices.data
        ]
    except stripe.error.StripeError:
        return []


# ── POST /billing/stripe-webhook ──────────────────────────────────────────────

@router.post(
    "/stripe-webhook",
    summary="Webhook Stripe — paiement facture",
    include_in_schema=False,
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook secret not configured",
        )

    _configure_stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    if event["type"] == "invoice.payment_succeeded":
        invoice_obj = event["data"]["object"]
        customer_id = invoice_obj.get("customer")
        if customer_id:
            tenant = (await db.execute(
                select(Tenant).where(Tenant.stripe_customer_id == customer_id)
            )).scalar_one_or_none()
            if tenant:
                lic = (await db.execute(
                    select(License)
                    .where(License.tenant_id == tenant.id)
                    .order_by(License.created_at.desc())
                )).scalars().first()
                if lic:
                    lic.status = "active"
                tenant.license_status = "active"
                await db.commit()
        _log.info("Stripe invoice.payment_succeeded: %s", invoice_obj.get("id"))

    elif event["type"] == "invoice.payment_failed":
        invoice_obj = event["data"]["object"]
        _log.warning(
            "Stripe invoice.payment_failed: customer=%s invoice=%s amount=%s",
            invoice_obj.get("customer"),
            invoice_obj.get("id"),
            invoice_obj.get("amount_due"),
        )

    return {"received": True}
