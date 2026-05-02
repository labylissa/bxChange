import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

ALLOWED_INVITE_ROLES = {"admin", "developer", "viewer"}


class TeamMemberRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class TeamInvite(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "developer"


class TeamRoleUpdate(BaseModel):
    role: str


class TeamMemberUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None


class TeamResetPasswordResponse(BaseModel):
    temp_password: str
