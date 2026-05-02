import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "admin@acme-corp.io",
            "password": "SecurePass123!",
            "full_name": "Jean Dupont",
        }
    })

    email: EmailStr
    password: str
    full_name: str | None = None


class UserLogin(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "admin@acme-corp.io",
            "password": "SecurePass123!",
        }
    })

    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    tenant_id: uuid.UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "current_password": "AncienMotDePasse123!",
            "new_password": "NouveauMotDePasse456!",
        }
    })

    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "full_name": "Jean Dupont",
            "email": "jean.dupont@acme-corp.io",
        }
    })

    full_name: str | None = None
    email: EmailStr | None = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
