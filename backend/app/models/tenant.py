import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # License
    license_status: Mapped[str] = mapped_column(
        Enum("trial", "active", "expired", "suspended", name="license_status_enum"),
        default="trial",
        nullable=False,
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Quotas (configured by super-admin per contract)
    executions_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    connectors_limit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    contract_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    contract_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    annual_price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Counters (reset monthly / maintained on create+delete)
    executions_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    connectors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Stripe (billing only)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
