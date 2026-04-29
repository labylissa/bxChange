import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _strip_tz(v: datetime | None) -> datetime | None:
    """Convert timezone-aware datetime to naive UTC (all DB columns are TIMESTAMP WITHOUT TIME ZONE)."""
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.replace(tzinfo=None)
    return v


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Clé production CRM",
            "rate_limit": 1000,
            "permissions": {"connectors": ["execute"]},
            "expires_at": None,
        }
    })

    name: str
    permissions: dict | None = None
    rate_limit: int | None = None
    expires_at: datetime | None = None

    @field_validator("expires_at", mode="after")
    @classmethod
    def normalize_expires_at(cls, v: datetime | None) -> datetime | None:
        return _strip_tz(v)


class ApiKeyRead(BaseModel):
    id: uuid.UUID
    name: str
    permissions: dict | None
    rate_limit: int | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreated(ApiKeyRead):
    raw_key: str
