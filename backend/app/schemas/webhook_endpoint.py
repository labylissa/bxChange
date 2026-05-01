import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

VALID_EVENTS = frozenset({"execution.success", "execution.failure", "execution.all"})


class WebhookEndpointCreate(BaseModel):
    name: str
    url: str
    secret: str = Field(min_length=16)
    events: list[str]
    connector_id: uuid.UUID

    @field_validator("url")
    @classmethod
    def url_must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("URL must start with https://")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one event must be specified")
        invalid = set(v) - VALID_EVENTS
        if invalid:
            raise ValueError(f"Invalid events: {invalid}. Valid: {VALID_EVENTS}")
        return v


class WebhookEndpointRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    connector_id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    url: str
    events: list[str]
    is_active: bool
    last_triggered_at: datetime | None
    last_status_code: int | None
    created_at: datetime


class WebhookEndpointUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    secret: str | None = Field(default=None, min_length=16)
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def url_must_be_https(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("https://"):
            raise ValueError("URL must start with https://")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            if not v:
                raise ValueError("At least one event must be specified")
            invalid = set(v) - VALID_EVENTS
            if invalid:
                raise ValueError(f"Invalid events: {invalid}. Valid: {VALID_EVENTS}")
        return v
