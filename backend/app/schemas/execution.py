import uuid
from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}
