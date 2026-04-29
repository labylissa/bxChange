import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExecutionRead(BaseModel):
    id: uuid.UUID
    connector_id: uuid.UUID
    status: str
    duration_ms: int | None
    request_payload: dict | None
    response_payload: dict | None
    error_message: str | None
    http_status: int | None
    triggered_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "params": {"intA": 10, "intB": 20},
            "body": None,
            "transform_override": {"rename": {"AddResult": "result"}},
        }
    })

    params: dict = Field(default_factory=dict)
    body: dict | None = None
    transform_override: dict | None = None


class ExecuteResponse(BaseModel):
    execution_id: uuid.UUID
    status: str
    result: dict | None
    duration_ms: int | None
    error_message: str | None = None
