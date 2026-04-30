"""
SCIM 2.0 Service — handles user provisioning via Azure AD / Okta.

Auth: Bearer token matched against scim_tokens.token_hash (SHA-256).
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.scim_token import ScimToken
from app.models.user import User
from app.schemas.scim import (
    SCIMListResponse,
    SCIMPatchOperation,
    SCIMPatchRequest,
    SCIMUserCreate,
    SCIMUserRead,
    SCIMUserUpdate,
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_scim_tenant(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """
    Validate Bearer token from Authorization header.
    Returns tenant_id for the matching ScimToken.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SCIM requires Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raw_token = auth[7:]
    token_hash = _hash_token(raw_token)

    result = await db.execute(
        select(ScimToken).where(
            ScimToken.token_hash == token_hash,
            ScimToken.is_active == True,
        )
    )
    scim_token = result.scalar_one_or_none()
    if scim_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked SCIM token",
        )
    now = datetime.now(timezone.utc)
    if scim_token.expires_at and scim_token.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SCIM token has expired",
        )
    return scim_token.tenant_id


# ── User helpers ──────────────────────────────────────────────────────────────

def _user_to_scim(user: User, base_url: str) -> SCIMUserRead:
    from app.schemas.scim import SCIMEmail, SCIMName
    return SCIMUserRead(
        id=str(user.id),
        userName=user.email,
        displayName=user.full_name,
        name=SCIMName(formatted=user.full_name) if user.full_name else None,
        emails=[SCIMEmail(value=user.email, type="work", primary=True)],
        active=user.is_active,
        meta={
            "resourceType": "User",
            "location": f"{base_url}/v2/Users/{user.id}",
            "created": user.created_at.isoformat() if user.created_at else None,
        },
    )


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/v1/scim"


# ── SCIM User operations ──────────────────────────────────────────────────────

async def list_users(
    tenant_id: uuid.UUID,
    db: AsyncSession,
    request: Request,
    filter_str: str | None = None,
    start_index: int = 1,
    count: int = 100,
) -> SCIMListResponse:
    query = select(User).where(User.tenant_id == tenant_id)

    # Basic filter support: filter=userName eq "email"
    if filter_str:
        parts = filter_str.split()
        if len(parts) == 3 and parts[0].lower() == "username" and parts[1].lower() == "eq":
            email_val = parts[2].strip('"\'')
            query = query.where(User.email == email_val)

    result = await db.execute(query)
    users = result.scalars().all()
    total = len(users)

    # Paginate
    page = users[start_index - 1: start_index - 1 + count]
    base = _base_url(request)

    return SCIMListResponse(
        totalResults=total,
        startIndex=start_index,
        itemsPerPage=len(page),
        Resources=[_user_to_scim(u, base).model_dump() for u in page],
    )


async def get_user(
    user_id: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    request: Request,
) -> SCIMUserRead:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(
        select(User).where(User.id == uid, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_scim(user, _base_url(request))


async def create_user(
    payload: SCIMUserCreate,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    request: Request,
) -> SCIMUserRead:
    email = payload.primary_email.lower().strip()

    # Check duplicate
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {email} already exists",
        )

    # Check quota
    from app.models.subscription import Subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    subscription = sub_result.scalar_one_or_none()
    if subscription:
        count_result = await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.is_active == True)
        )
        current_count = len(count_result.scalars().all())
        if current_count >= subscription.users_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant user limit reached",
            )

    full_name = None
    if payload.name:
        full_name = payload.name.formatted or (
            f"{payload.name.givenName or ''} {payload.name.familyName or ''}".strip()
        )
    full_name = full_name or payload.displayName or email.split("@")[0]

    new_user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="!scim:" + hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        full_name=full_name,
        tenant_id=tenant_id,
        role="viewer",
        is_active=payload.active,
        created_at=datetime.utcnow(),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return _user_to_scim(new_user, _base_url(request))


async def update_user(
    user_id: str,
    payload: SCIMUserUpdate,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    request: Request,
) -> SCIMUserRead:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(
        select(User).where(User.id == uid, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.active is not None:
        user.is_active = payload.active
    if payload.displayName is not None:
        user.full_name = payload.displayName
    if payload.name and payload.name.formatted:
        user.full_name = payload.name.formatted

    await db.commit()
    await db.refresh(user)
    return _user_to_scim(user, _base_url(request))


async def patch_user(
    user_id: str,
    patch: SCIMPatchRequest,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    request: Request,
) -> SCIMUserRead:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(
        select(User).where(User.id == uid, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    for op in patch.Operations:
        op_lower = op.op.lower()
        path = (op.path or "").lower()

        if path == "active" or (op_lower in ("add", "replace") and isinstance(op.value, dict) and "active" in op.value):
            val = op.value if path == "active" else op.value.get("active")
            if val is not None:
                user.is_active = bool(val)

        if path == "displayname" or (isinstance(op.value, dict) and "displayName" in op.value):
            val = op.value if path == "displayname" else op.value.get("displayName")
            if val:
                user.full_name = val

    await db.commit()
    await db.refresh(user)
    return _user_to_scim(user, _base_url(request))


async def delete_user(
    user_id: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(
        select(User).where(User.id == uid, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await db.commit()


