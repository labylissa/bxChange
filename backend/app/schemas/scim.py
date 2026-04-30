"""
SCIM 2.0 schemas (RFC 7643 / RFC 7644).
We support the core User resource and a minimal Group resource.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


# ── Shared helpers ────────────────────────────────────────────────────────────

class SCIMName(BaseModel):
    formatted: str | None = None
    givenName: str | None = None
    familyName: str | None = None


class SCIMEmail(BaseModel):
    value: str
    type: str = "work"
    primary: bool = False


class SCIMMember(BaseModel):
    value: str          # user id
    display: str | None = None


# ── SCIM User ─────────────────────────────────────────────────────────────────

class SCIMUserCreate(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    userName: str
    name: SCIMName | None = None
    emails: list[SCIMEmail] = []
    active: bool = True
    externalId: str | None = None
    displayName: str | None = None

    @property
    def primary_email(self) -> str:
        for e in self.emails:
            if e.primary:
                return e.value
        if self.emails:
            return self.emails[0].value
        return self.userName


class SCIMUserUpdate(BaseModel):
    """Full replacement (PUT) or partial patch (PATCH) payload."""
    schemas: list[str] | None = None
    userName: str | None = None
    name: SCIMName | None = None
    emails: list[SCIMEmail] | None = None
    active: bool | None = None
    displayName: str | None = None


class SCIMUserRead(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    id: str
    userName: str
    name: SCIMName | None = None
    emails: list[SCIMEmail] = []
    active: bool
    externalId: str | None = None
    displayName: str | None = None
    meta: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


# ── SCIM Group ────────────────────────────────────────────────────────────────

class SCIMGroupCreate(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    displayName: str
    members: list[SCIMMember] = []
    externalId: str | None = None


class SCIMGroupRead(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    id: str
    displayName: str
    members: list[SCIMMember] = []
    externalId: str | None = None
    meta: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


# ── SCIM Patch ────────────────────────────────────────────────────────────────

class SCIMPatchOperation(BaseModel):
    op: str           # "add" | "replace" | "remove"
    path: str | None = None
    value: Any = None


class SCIMPatchRequest(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
    Operations: list[SCIMPatchOperation]


# ── SCIM List Response ────────────────────────────────────────────────────────

class SCIMListResponse(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int
    Resources: list[Any] = []


# ── SCIM Error ────────────────────────────────────────────────────────────────

class SCIMError(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:api:messages:2.0:Error"]
    status: str
    detail: str | None = None
    scimType: str | None = None
