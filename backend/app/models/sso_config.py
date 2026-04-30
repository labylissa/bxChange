import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SSOConfig(Base):
    __tablename__ = "sso_configs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    idp_type: Mapped[str] = mapped_column(
        Enum("saml", "oidc", name="idp_type"), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(String(512), nullable=False)
    sso_url: Mapped[str] = mapped_column(String(512), nullable=False)
    # IdP X.509 cert (SAML) or client_secret (OIDC) — encrypted via crypto.encrypt
    certificate: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"email_attr": ..., "name_attr": ..., "groups_attr": ..., "role_mapping": {...}}
    attr_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
