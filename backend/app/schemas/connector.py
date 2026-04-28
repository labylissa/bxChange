import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, model_validator


class ConnectorType(str, Enum):
    soap = "soap"
    rest = "rest"


class AuthType(str, Enum):
    none = "none"
    basic = "basic"
    bearer = "bearer"
    apikey = "apikey"
    oauth2 = "oauth2"


class ConnectorStatus(str, Enum):
    active = "active"
    error = "error"
    disabled = "disabled"
    draft = "draft"


class ConnectorCreate(BaseModel):
    name: str
    type: ConnectorType
    base_url: str | None = None
    wsdl_url: str | None = None
    auth_type: AuthType = AuthType.none
    auth_config: dict | None = None
    headers: dict | None = None
    transform_config: dict | None = None

    @model_validator(mode="after")
    def validate_type_fields(self) -> "ConnectorCreate":
        if self.type == ConnectorType.soap and not self.wsdl_url:
            raise ValueError("SOAP connectors require wsdl_url")
        if self.type == ConnectorType.rest and not self.base_url:
            raise ValueError("REST connectors require base_url")
        return self


class ConnectorRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    type: str
    base_url: str | None
    wsdl_url: str | None
    auth_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectorUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    wsdl_url: str | None = None
    auth_type: AuthType | None = None
    auth_config: dict | None = None
    headers: dict | None = None
    transform_config: dict | None = None
    status: ConnectorStatus | None = None


class WSDLParseResult(BaseModel):
    operations: dict[str, dict]
    count: int


class RestTestPayload(BaseModel):
    method: str = "GET"
    path: str = ""
    params: dict | None = None
    body: dict | None = None


class PreviewTransformPayload(BaseModel):
    raw_xml: str
    transform_config: dict | None = None
