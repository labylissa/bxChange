"""Team management API — admins managing their own tenant's users."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_admin_or_above
from app.core.security import hash_password
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.team import ALLOWED_INVITE_ROLES, TeamInvite, TeamMemberRead, TeamRoleUpdate

router = APIRouter(prefix="/team", tags=["team"])

_401 = {"description": "Token invalide ou expiré"}
_403 = {"description": "Rôle admin requis"}
_404 = {"description": "Membre introuvable"}


@router.get(
    "/members",
    response_model=list[TeamMemberRead],
    summary="Membres du tenant",
    description="Retourne la liste de tous les utilisateurs du tenant courant. Requiert le rôle **admin**.",
    responses={200: {"description": "Liste des membres"}, 401: _401, 403: _403},
)
async def list_members(
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> list[TeamMemberRead]:
    users = (await db.execute(
        select(User).where(User.tenant_id == current_user.tenant_id)
    )).scalars().all()
    return [TeamMemberRead.model_validate(u) for u in users]


@router.post(
    "/invite",
    response_model=TeamMemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Inviter un membre",
    description=(
        "Crée un nouvel utilisateur dans le tenant courant. "
        "Le quota `users_limit` est vérifié avant la création (403 si atteint). "
        "Rôles disponibles : `admin` | `developer` | `viewer`."
    ),
    responses={
        201: {"description": "Membre créé"},
        401: _401,
        403: {"description": "Quota d'utilisateurs atteint ou rôle insuffisant"},
        409: {"description": "Email déjà utilisé"},
        422: {"description": "Rôle invalide"},
    },
)
async def invite_member(
    payload: TeamInvite,
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberRead:
    if payload.role not in ALLOWED_INVITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Role must be one of: {', '.join(sorted(ALLOWED_INVITE_ROLES))}",
        )

    sub = (await db.execute(
        select(Subscription).where(Subscription.tenant_id == current_user.tenant_id)
    )).scalar_one_or_none()

    if sub and sub.users_limit is not None:
        user_count = (await db.execute(
            select(func.count(User.id)).where(User.tenant_id == current_user.tenant_id)
        )).scalar_one()
        if user_count >= sub.users_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Quota atteint : votre plan autorise {sub.users_limit} utilisateurs. "
                    "Contactez votre administrateur."
                ),
            )

    existing = (await db.execute(
        select(User).where(User.email == payload.email)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    new_user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        tenant_id=current_user.tenant_id,
        role=payload.role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return TeamMemberRead.model_validate(new_user)


@router.patch(
    "/members/{member_id}/role",
    response_model=TeamMemberRead,
    summary="Changer le rôle d'un membre",
    description=(
        "Modifie le rôle d'un membre du tenant. "
        "Il n'est pas possible de modifier un `super_admin`."
    ),
    responses={
        200: {"description": "Rôle mis à jour"},
        401: _401,
        403: {"description": "Rôle admin requis ou membre super_admin non modifiable"},
        404: _404,
        422: {"description": "Rôle invalide"},
    },
)
async def update_member_role(
    member_id: uuid.UUID,
    payload: TeamRoleUpdate,
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberRead:
    if payload.role not in ALLOWED_INVITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Role must be one of: {', '.join(sorted(ALLOWED_INVITE_ROLES))}",
        )

    member = (await db.execute(
        select(User).where(User.id == member_id, User.tenant_id == current_user.tenant_id)
    )).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.role == "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Cannot modify a super admin")

    member.role = payload.role
    await db.commit()
    await db.refresh(member)
    return TeamMemberRead.model_validate(member)


@router.patch(
    "/members/{member_id}/deactivate",
    response_model=TeamMemberRead,
    summary="Désactiver un membre",
    description="Désactive un membre du tenant. Un admin ne peut pas se désactiver lui-même.",
    responses={
        200: {"description": "Membre désactivé"},
        401: _401,
        403: {"description": "Impossible de se désactiver soi-même"},
        404: _404,
    },
)
async def deactivate_member(
    member_id: uuid.UUID,
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberRead:
    member = (await db.execute(
        select(User).where(User.id == member_id, User.tenant_id == current_user.tenant_id)
    )).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Cannot deactivate yourself")

    member.is_active = False
    await db.commit()
    await db.refresh(member)
    return TeamMemberRead.model_validate(member)
