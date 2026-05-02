"""Super Admin — License management + Stripe invoicing."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db, require_super_admin
from app.models.license import License
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.license import (
    InvoiceCreate,
    InvoiceResponse,
    LicenseCreate,
    LicenseRead,
    LicenseUpdate,
    RenewRequest,
    SuspendRequest,
    TenantUsageAdmin,
)

router = APIRouter(prefix="/admin", tags=["admin"])

_401 = {"description": "Token invalide ou expiré"}
_403 = {"description": "Rôle super_admin requis"}
_404 = {"description": "Licence introuvable"}


def _configure_stripe() -> None:
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key


async def _get_license_or_404(license_id: uuid.UUID, db: AsyncSession) -> License:
    lic = (await db.execute(
        select(License).where(License.id == license_id)
    )).scalar_one_or_none()
    if lic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    return lic


def _days_remaining(contract_end: datetime | None) -> int | None:
    if contract_end is None:
        return None
    delta = contract_end - datetime.utcnow()
    return max(0, delta.days)


# ── Licenses CRUD ──────────────────────────────────────────────────────────────

@router.get(
    "/licenses",
    response_model=list[LicenseRead],
    summary="Lister toutes les licences",
    responses={200: {"description": "Liste des licences"}, 401: _401, 403: _403},
)
async def list_licenses(
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[LicenseRead]:
    licenses = (await db.execute(select(License))).scalars().all()
    return [LicenseRead.model_validate(lic) for lic in licenses]


@router.post(
    "/licenses",
    response_model=LicenseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une licence pour un tenant",
    responses={
        201: {"description": "Licence créée"},
        401: _401,
        403: _403,
        404: {"description": "Tenant introuvable"},
    },
)
async def create_license(
    payload: LicenseCreate,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> LicenseRead:
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == payload.tenant_id)
    )).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Get tenant admin email for Stripe customer
    admin = (await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.role == "admin")
    )).scalars().first()

    # Create Stripe customer if not exists
    _configure_stripe()
    if settings.stripe_secret_key and not tenant.stripe_customer_id:
        try:
            customer = stripe.Customer.create(
                email=admin.email if admin else None,
                name=tenant.name,
                metadata={"tenant_id": str(tenant.id)},
            )
            tenant.stripe_customer_id = customer.id
        except Exception:
            pass

    # Create license record
    license_key = f"bxc_lic_{secrets.token_urlsafe(16)}"
    lic = License(
        tenant_id=tenant.id,
        license_key=license_key,
        status="trial",
        executions_limit=payload.executions_limit,
        connectors_limit=payload.connectors_limit,
        contract_start=payload.contract_start,
        contract_end=payload.contract_end,
        annual_price_cents=payload.annual_price_cents,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(lic)

    # Update tenant quotas immediately
    tenant.executions_limit = payload.executions_limit
    tenant.connectors_limit = payload.connectors_limit
    tenant.contract_start = payload.contract_start
    tenant.contract_end = payload.contract_end
    tenant.annual_price_cents = payload.annual_price_cents

    await db.commit()
    await db.refresh(lic)
    return LicenseRead.model_validate(lic)


@router.get(
    "/licenses/{license_id}",
    response_model=LicenseRead,
    summary="Détail d'une licence",
    responses={200: {"description": "Licence"}, 401: _401, 403: _403, 404: _404},
)
async def get_license(
    license_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> LicenseRead:
    return LicenseRead.model_validate(await _get_license_or_404(license_id, db))


@router.put(
    "/licenses/{license_id}",
    response_model=LicenseRead,
    summary="Modifier une licence",
    responses={200: {"description": "Licence mise à jour"}, 401: _401, 403: _403, 404: _404},
)
async def update_license(
    license_id: uuid.UUID,
    payload: LicenseUpdate,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> LicenseRead:
    lic = await _get_license_or_404(license_id, db)
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == lic.tenant_id)
    )).scalar_one_or_none()

    if payload.executions_limit is not None:
        lic.executions_limit = payload.executions_limit
        if tenant:
            tenant.executions_limit = payload.executions_limit
    if payload.connectors_limit is not None:
        lic.connectors_limit = payload.connectors_limit
        if tenant:
            tenant.connectors_limit = payload.connectors_limit
    if payload.contract_start is not None:
        lic.contract_start = payload.contract_start
        if tenant:
            tenant.contract_start = payload.contract_start
    if payload.contract_end is not None:
        lic.contract_end = payload.contract_end
        if tenant:
            tenant.contract_end = payload.contract_end
    if payload.annual_price_cents is not None:
        lic.annual_price_cents = payload.annual_price_cents
        if tenant:
            tenant.annual_price_cents = payload.annual_price_cents
    if payload.notes is not None:
        lic.notes = payload.notes

    await db.commit()
    await db.refresh(lic)
    return LicenseRead.model_validate(lic)


@router.post(
    "/licenses/{license_id}/activate",
    response_model=LicenseRead,
    summary="Activer une licence (trial → active)",
    responses={200: {"description": "Licence activée"}, 401: _401, 403: _403, 404: _404},
)
async def activate_license(
    license_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> LicenseRead:
    lic = await _get_license_or_404(license_id, db)
    lic.status = "active"
    lic.activated_at = datetime.utcnow()

    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == lic.tenant_id)
    )).scalar_one_or_none()
    if tenant:
        tenant.license_status = "active"
        tenant.trial_ends_at = None

    await db.commit()
    await db.refresh(lic)
    return LicenseRead.model_validate(lic)


@router.post(
    "/licenses/{license_id}/suspend",
    response_model=LicenseRead,
    summary="Suspendre une licence",
    responses={200: {"description": "Licence suspendue"}, 401: _401, 403: _403, 404: _404},
)
async def suspend_license(
    license_id: uuid.UUID,
    payload: SuspendRequest,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> LicenseRead:
    lic = await _get_license_or_404(license_id, db)
    lic.status = "suspended"
    lic.suspended_at = datetime.utcnow()
    lic.suspension_reason = payload.reason

    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == lic.tenant_id)
    )).scalar_one_or_none()
    if tenant:
        tenant.license_status = "suspended"

    await db.commit()
    await db.refresh(lic)
    return LicenseRead.model_validate(lic)


@router.post(
    "/licenses/{license_id}/renew",
    response_model=LicenseRead,
    summary="Renouveler une licence (+1 an)",
    responses={200: {"description": "Licence renouvelée"}, 401: _401, 403: _403, 404: _404},
)
async def renew_license(
    license_id: uuid.UUID,
    payload: RenewRequest,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> LicenseRead:
    lic = await _get_license_or_404(license_id, db)

    new_end = lic.contract_end + timedelta(days=payload.extension_days)
    lic.contract_end = new_end
    lic.status = "active"
    lic.activated_at = lic.activated_at or datetime.utcnow()
    if payload.new_annual_price_cents is not None:
        lic.annual_price_cents = payload.new_annual_price_cents

    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == lic.tenant_id)
    )).scalar_one_or_none()
    if tenant:
        tenant.license_status = "active"
        tenant.contract_end = new_end
        if payload.new_annual_price_cents is not None:
            tenant.annual_price_cents = payload.new_annual_price_cents

    await db.commit()
    await db.refresh(lic)
    return LicenseRead.model_validate(lic)


# ── Tenant usage ───────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenant_id}/usage",
    response_model=TenantUsageAdmin,
    summary="Usage détaillé d'un tenant",
    responses={200: {"description": "Usage"}, 401: _401, 403: _403, 404: {"description": "Tenant introuvable"}},
)
async def get_tenant_usage(
    tenant_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantUsageAdmin:
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    pct = (tenant.executions_used / tenant.executions_limit * 100) if tenant.executions_limit > 0 else 0.0
    return TenantUsageAdmin(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        license_status=tenant.license_status,
        executions_used=tenant.executions_used,
        executions_limit=tenant.executions_limit,
        executions_pct=round(pct, 1),
        connectors_count=tenant.connectors_count,
        connectors_limit=tenant.connectors_limit,
        contract_start=tenant.contract_start,
        contract_end=tenant.contract_end,
        days_remaining=_days_remaining(tenant.contract_end),
        trial_ends_at=tenant.trial_ends_at,
        stripe_customer_id=tenant.stripe_customer_id,
        annual_price_cents=tenant.annual_price_cents,
    )


# ── Stripe invoicing ───────────────────────────────────────────────────────────

@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer et envoyer une facture Stripe",
    responses={
        201: {"description": "Facture envoyée"},
        400: {"description": "Stripe non configuré ou erreur"},
        401: _401,
        403: _403,
        404: {"description": "Tenant introuvable"},
    },
)
async def create_invoice(
    payload: InvoiceCreate,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    _configure_stripe()
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe non configuré (STRIPE_SECRET_KEY manquant)",
        )

    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == payload.tenant_id)
    )).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if not tenant.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce tenant n'a pas de customer Stripe. Créez d'abord une licence.",
        )

    try:
        from datetime import date
        due = date.fromisoformat(payload.due_date)
        now = date.today()
        days_until_due = max(1, (due - now).days)

        invoice = stripe.Invoice.create(
            customer=tenant.stripe_customer_id,
            collection_method="send_invoice",
            days_until_due=days_until_due,
            currency="eur",
            auto_advance=False,
        )
        stripe.InvoiceItem.create(
            customer=tenant.stripe_customer_id,
            invoice=invoice.id,
            amount=payload.amount_cents,
            currency="eur",
            description=payload.description,
        )
        finalized = stripe.Invoice.finalize_invoice(invoice.id)
        stripe.Invoice.send_invoice(finalized.id)

        return InvoiceResponse(
            invoice_id=finalized.id,
            invoice_url=finalized.get("hosted_invoice_url"),
            pdf_url=finalized.get("invoice_pdf"),
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur Stripe : {exc.user_message or str(exc)}",
        )
