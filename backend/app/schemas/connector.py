import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Advanced config sub-schemas ────────────────────────────────────────────────

class WSSecurityConfig(BaseModel):
    type: Literal["username_token", "certificate"]
    username: str | None = None
    password: str | None = None
    timestamp: bool = True
    nonce: bool = True


class SOAPAdvancedConfig(BaseModel):
    service_name: str | None = None
    port_name: str | None = None
    operation_timeout: int = 30
    custom_headers: dict[str, str] = Field(default_factory=dict)
    ws_security: WSSecurityConfig | None = None
    response_path: str | None = None
    force_list_paths: list[str] = Field(default_factory=list)


class OAuth2CCConfig(BaseModel):
    token_url: str
    client_id: str
    client_secret: str
    scope: str | None = None
    token_cache_ttl: int = 3600


class RESTAdvancedConfig(BaseModel):
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    retry_count: int = 3
    retry_backoff: float = 1.0
    retry_on_codes: list[int] = Field(default_factory=lambda: [429, 502, 503, 504])
    response_path: str | None = None
    body_template: str | None = None
    oauth2_client_credentials: OAuth2CCConfig | None = None


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


class WsdlSource(str, Enum):
    url = "url"
    upload = "upload"


class ConnectorCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Calculator SOAP",
            "type": "soap",
            "wsdl_url": "http://www.dneonline.com/calculator.asmx?WSDL",
            "wsdl_source": "url",
            "operation": "Add",
            "auth_type": "none",
            "auth_config": {},
            "headers": {},
            "transform_config": {"rename": {"AddResult": "result"}},
        }
    })

    name: str
    type: ConnectorType
    base_url: str | None = None
    wsdl_url: str | None = None
    wsdl_source: WsdlSource = WsdlSource.url
    wsdl_file_id: str | None = None
    operation: str | None = None
    auth_type: AuthType = AuthType.none
    auth_config: dict | None = None
    headers: dict | None = None
    transform_config: dict | None = None
    advanced_config: dict | None = None

    @model_validator(mode="after")
    def validate_type_fields(self) -> "ConnectorCreate":
        if self.type == ConnectorType.soap:
            if self.wsdl_source == WsdlSource.url and not self.wsdl_url:
                raise ValueError("SOAP connectors with wsdl_source=url require wsdl_url")
            if self.wsdl_source == WsdlSource.upload and not self.wsdl_file_id:
                raise ValueError("SOAP connectors with wsdl_source=upload require wsdl_file_id")
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
    wsdl_source: str
    wsdl_file_path: str | None
    operation: str | None = None
    auth_type: str
    status: str
    headers: dict | None = None
    transform_config: dict | None = None
    advanced_config: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConnectorUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    wsdl_url: str | None = None
    operation: str | None = None
    auth_type: AuthType | None = None
    auth_config: dict | None = None
    headers: dict | None = None
    transform_config: dict | None = None
    advanced_config: dict | None = None
    status: ConnectorStatus | None = None


class WSDLParseResult(BaseModel):
    operations: dict[str, dict]
    count: int


class WsdlUploadResult(BaseModel):
    wsdl_file_id: str
    wsdl_file_path: str
    operations: list[str]
    filename: str


class RestTestPayload(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "method": "GET",
            "path": "/posts/1",
            "params": None,
            "body": None,
        }
    })

    method: str = "GET"
    path: str = ""
    params: dict | None = None
    body: dict | None = None


class PreviewTransformPayload(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "raw_xml": "<AddResult>70</AddResult>",
            "transform_config": {"rename": {"AddResult": "result"}},
        }
    })

    raw_xml: str
    transform_config: dict | None = None


class SnippetResponse(BaseModel):
    lang: str
    connector_id: str
    connector_name: str
    snippet: str
