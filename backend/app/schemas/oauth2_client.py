import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


VALID_SCOPES = {"execute:connectors", "execute:pipelines", "read:results"}


class OAuth2ClientCreate(BaseModel):
    name: str
    scopes: list[str] = ["execute:connectors"]
    token_ttl_seconds: int = 3600
    allowed_ips: list[str] = []

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_SCOPES
        if invalid:
            raise ValueError(f"Scopes invalides : {invalid}. Valides : {VALID_SCOPES}")
        if not v:
            raise ValueError("Au moins un scope est requis")
        return v

    @field_validator("token_ttl_seconds")
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        if not (60 <= v <= 86400):
            raise ValueError("token_ttl_seconds doit être entre 60 et 86400")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Système CovéaProd",
                "scopes": ["execute:connectors", "execute:pipelines"],
                "token_ttl_seconds": 3600,
                "allowed_ips": ["192.168.1.0/24"],
            }
        }
    }


class OAuth2ClientUpdate(BaseModel):
    name: Optional[str] = None
    scopes: Optional[list[str]] = None
    token_ttl_seconds: Optional[int] = None
    allowed_ips: Optional[list[str]] = None
    is_active: Optional[bool] = None

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = set(v) - VALID_SCOPES
            if invalid:
                raise ValueError(f"Scopes invalides : {invalid}")
        return v


class OAuth2ClientRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: str
    client_secret_preview: str
    name: str
    scopes: list[str]
    is_active: bool
    token_ttl_seconds: int
    allowed_ips: list[str]
    last_used_at: Optional[datetime]
    created_at: datetime
    created_by: uuid.UUID

    model_config = {"from_attributes": True}


class OAuth2ClientCreated(OAuth2ClientRead):
    client_secret: str
