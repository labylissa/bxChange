from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LicenseCreate(BaseModel):
    tenant_id: uuid.UUID
    executions_limit: int = 1000
    connectors_limit: int = 5
    contract_start: datetime
    contract_end: datetime
    annual_price_cents: int = 0
    notes: str | None = None


class LicenseRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    license_key: str
    status: str
    executions_limit: int
    connectors_limit: int
    contract_start: datetime
    contract_end: datetime
    annual_price_cents: int
    notes: str | None
    created_by: uuid.UUID
    created_at: datetime
    activated_at: datetime | None
    suspended_at: datetime | None
    suspension_reason: str | None

    model_config = ConfigDict(from_attributes=True)


class LicenseUpdate(BaseModel):
    executions_limit: int | None = None
    connectors_limit: int | None = None
    contract_start: datetime | None = None
    contract_end: datetime | None = None
    annual_price_cents: int | None = None
    notes: str | None = None


class SuspendRequest(BaseModel):
    reason: str


class RenewRequest(BaseModel):
    new_annual_price_cents: int | None = None
    extension_days: int = 365


class InvoiceCreate(BaseModel):
    tenant_id: uuid.UUID
    description: str
    amount_cents: int
    due_date: str


class InvoiceResponse(BaseModel):
    invoice_id: str
    invoice_url: str | None
    pdf_url: str | None


class BillingUsage(BaseModel):
    license_status: str
    executions_used: int
    executions_limit: int
    executions_pct: float
    connectors_used: int
    connectors_limit: int
    contract_end: datetime | None
    days_remaining: int | None
    trial_ends_at: datetime | None


class TenantUsageAdmin(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    license_status: str
    executions_used: int
    executions_limit: int
    executions_pct: float
    connectors_count: int
    connectors_limit: int
    contract_start: datetime | None
    contract_end: datetime | None
    days_remaining: int | None
    trial_ends_at: datetime | None
    stripe_customer_id: str | None
    annual_price_cents: int
