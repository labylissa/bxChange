import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class IdpType(str, Enum):
    saml = "saml"
    oidc = "oidc"


# ── SSO Config ────────────────────────────────────────────────────────────────

class SSOConfigCreate(BaseModel):
    idp_type: IdpType
    entity_id: str
    sso_url: str
    certificate: str | None = None   # Raw PEM cert — encrypted at write time
    attr_mapping: dict | None = None
    domains: list[str] = []          # Email domains that trigger SSO auto-redirect


class SSOConfigUpdate(BaseModel):
    entity_id: str | None = None
    sso_url: str | None = None
    certificate: str | None = None
    attr_mapping: dict | None = None
    is_active: bool | None = None
    domains: list[str] | None = None


class SSOConfigRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    idp_type: str
    entity_id: str
    sso_url: str
    attr_mapping: dict | None
    is_active: bool
    created_at: datetime
    # certificate and domains are never returned in reads for security

    model_config = ConfigDict(from_attributes=True)


# ── SCIM Token ────────────────────────────────────────────────────────────────

class ScimTokenCreate(BaseModel):
    name: str
    expires_at: datetime | None = None


class ScimTokenRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScimTokenCreated(ScimTokenRead):
    raw_token: str  # shown only once at creation


# ── Domain hint ───────────────────────────────────────────────────────────────

class DomainHintRead(BaseModel):
    domain: str
    sso_config_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


# ── SP Metadata ───────────────────────────────────────────────────────────────

class SPMetadata(BaseModel):
    entity_id: str
    acs_url: str
    metadata_xml: str
