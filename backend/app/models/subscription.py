import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    plan: Mapped[str] = mapped_column(
        Enum("starter", "professional", "enterprise", name="subscription_plan"),
        nullable=False,
    )
    stripe_sub_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "past_due", "cancelled", "trialing", name="subscription_status"),
        default="trialing",
        nullable=False,
    )
    connector_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calls_limit_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
