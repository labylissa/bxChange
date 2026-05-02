import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class TenantStats(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    plan: str | None
    subscription_status: str | None
    connector_limit: int | None
    users_limit: int | None
    connector_count: int
    user_count: int


class TenantCreate(BaseModel):
    company_name: str
    admin_email: EmailStr
    admin_name: str
    admin_password: str
    connector_limit: int = 10
    users_limit: int = 5


class QuotaUpdate(BaseModel):
    connector_limit: int
    users_limit: int


class UserInTenant(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectorInTenant(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantDetail(TenantStats):
    users: list[UserInTenant]
    connectors: list[ConnectorInTenant]


class AdminUserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    tenant_id: uuid.UUID | None
    tenant_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleUpdate(BaseModel):
    role: str


class ActivateUpdate(BaseModel):
    is_active: bool


class ImpersonateResponse(BaseModel):
    access_token: str
    user_id: str
    email: str
    expires_in: int


class QuotaRead(BaseModel):
    connector_count: int
    connector_limit: int | None
    user_count: int
    users_limit: int | None


class PlanUpdate(BaseModel):
    plan: str
    connector_limit: int | None = None
    users_limit: int | None = None
