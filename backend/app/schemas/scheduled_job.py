import uuid
from datetime import datetime, timedelta
from typing import Literal

from croniter import croniter as _croniter
from pydantic import BaseModel, ConfigDict, Field, model_validator


def compute_next_run(
    schedule_type: str,
    cron_expression: str | None,
    interval_seconds: int | None,
) -> datetime | None:
    now = datetime.utcnow()
    if schedule_type == "cron" and cron_expression:
        return _croniter(cron_expression, now).get_next(datetime)
    if schedule_type == "interval" and interval_seconds:
        return now + timedelta(seconds=interval_seconds)
    return None


class ScheduledJobCreate(BaseModel):
    connector_id: uuid.UUID
    name: str
    schedule_type: Literal["cron", "interval"]
    cron_expression: str | None = None
    interval_seconds: int | None = None
    input_params: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schedule(self) -> "ScheduledJobCreate":
        if self.schedule_type == "cron":
            if not self.cron_expression:
                raise ValueError("cron_expression is required when schedule_type=cron")
            if not _croniter.is_valid(self.cron_expression):
                raise ValueError(f"Invalid cron expression: {self.cron_expression!r}")
        if self.schedule_type == "interval":
            if self.interval_seconds is None:
                raise ValueError("interval_seconds is required when schedule_type=interval")
            if self.interval_seconds < 60:
                raise ValueError("interval_seconds must be >= 60")
        return self


class ScheduledJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connector_id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    schedule_type: str
    cron_expression: str | None
    interval_seconds: int | None
    input_params: dict
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    created_by: uuid.UUID | None
    connector_name: str | None = None


class ScheduledJobUpdate(BaseModel):
    name: str | None = None
    schedule_type: Literal["cron", "interval"] | None = None
    cron_expression: str | None = None
    interval_seconds: int | None = None
    input_params: dict | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "ScheduledJobUpdate":
        if self.cron_expression is not None and not _croniter.is_valid(self.cron_expression):
            raise ValueError(f"Invalid cron expression: {self.cron_expression!r}")
        if self.interval_seconds is not None and self.interval_seconds < 60:
            raise ValueError("interval_seconds must be >= 60")
        return self
