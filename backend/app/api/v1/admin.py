"""Super Admin API — full platform visibility and control."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_super_admin
from app.core.security import create_access_token, hash_password
from app.models.connector import Connector
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.admin import (
    ActivateUpdate,
    AdminUserRead,
    ImpersonateResponse,
    PlanUpdate,
    QuotaUpdate,
    RoleUpdate,
    TenantCreate,
    TenantDetail,
    TenantStats,
    UserInTenant,
    ConnectorInTenant,
)

router = APIRouter(prefix="/admin", tags=["admin"])

VALID_ROLES = {"super_admin", "admin", "developer", "viewer"}

_401 = {"description": "Token invalide ou expiré"}
_403 = {"description": "Rôle super_admin requis"}
_404_tenant = {"description": "Tenant introuvable"}
_404_user = {"description": "Utilisateur introuvable"}


async def _build_tenant_stats(tenant: Tenant, db: AsyncSession) -> TenantStats:
    user_count = (await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant.id)
    )).scalar_one()

    connector_count = (await db.execute(
        select(func.count(Connector.id)).where(Connector.tenant_id == tenant.id)
    )).scalar_one()

    sub = (await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant.id)
    )).scalar_one_or_none()

    return TenantStats(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        created_at=tenant.created_at,
        plan=sub.plan if sub else None,
        subscription_status=sub.status if sub else None,
        connector_limit=sub.connector_limit if sub else None,
        users_limit=sub.users_limit if sub else None,
        connector_count=connector_count,
        user_count=user_count,
    )


async def _get_tenant_or_404(tenant_id: uuid.UUID, db: AsyncSession) -> Tenant:
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@router.get(
    "/tenants",
    response_model=list[TenantStats],
    summary="Lister tous les tenants",
    description="Retourne la liste de tous les tenants avec leurs statistiques (users, connecteurs, plan).",
    responses={200: {"description": "Liste des tenants"}, 401: _401, 403: _403},
)
async def list_tenants(
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantStats]:
    tenants = (await db.execute(select(Tenant))).scalars().all()
    return [await _build_tenant_stats(t, db) for t in tenants]


@router.post(
    "/tenants",
    response_model=TenantStats,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un tenant",
    description=(
        "Crée un nouveau tenant avec son abonnement (plan starter) et son premier utilisateur admin. "
        "Le `connector_limit` et `users_limit` définissent les quotas du plan."
    ),
    responses={
        201: {"description": "Tenant créé"},
        401: _401,
        403: _403,
        409: {"description": "Email admin déjà utilisé"},
    },
)
async def create_tenant(
    payload: TenantCreate,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantStats:
    existing = (await db.execute(
        select(User).where(User.email == payload.admin_email)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    tenant = Tenant(
        name=payload.company_name,
        slug=str(uuid.uuid4()),
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
    )
    db.add(tenant)
    await db.flush()

    sub = Subscription(
        tenant_id=tenant.id,
        plan="starter",
        status="trialing",
        connector_limit=payload.connector_limit,
        users_limit=payload.users_limit,
    )
    db.add(sub)

    admin_user = User(
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        full_name=payload.admin_name,
        tenant_id=tenant.id,
        role="admin",
    )
    db.add(admin_user)
    await db.commit()
    await db.refresh(tenant)

    return await _build_tenant_stats(tenant, db)


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantDetail,
    summary="Détail d'un tenant",
    description="Retourne les informations complètes d'un tenant : utilisateurs, connecteurs, quotas.",
    responses={200: {"description": "Détail du tenant"}, 401: _401, 403: _403, 404: _404_tenant},
)
async def get_tenant(
    tenant_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantDetail:
    tenant = await _get_tenant_or_404(tenant_id, db)
    stats = await _build_tenant_stats(tenant, db)

    users = (await db.execute(
        select(User).where(User.tenant_id == tenant_id)
    )).scalars().all()

    connectors = (await db.execute(
        select(Connector).where(Connector.tenant_id == tenant_id)
    )).scalars().all()

    return TenantDetail(
        **stats.model_dump(),
        users=[UserInTenant.model_validate(u) for u in users],
        connectors=[ConnectorInTenant.model_validate(c) for c in connectors],
    )


@router.patch(
    "/tenants/{tenant_id}/quota",
    summary="Modifier les quotas d'un tenant",
    description="Met à jour les limites de connecteurs et d'utilisateurs du plan d'un tenant.",
    responses={
        200: {"description": "Quotas mis à jour"},
        401: _401,
        403: _403,
        404: _404_tenant,
    },
)
async def update_quota(
    tenant_id: uuid.UUID,
    payload: QuotaUpdate,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant = await _get_tenant_or_404(tenant_id, db)

    sub = (await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant.id)
    )).scalar_one_or_none()

    if sub is None:
        sub = Subscription(
            tenant_id=tenant.id,
            plan="starter",
            status="active",
            connector_limit=payload.connector_limit,
            users_limit=payload.users_limit,
        )
        db.add(sub)
    else:
        sub.connector_limit = payload.connector_limit
        sub.users_limit = payload.users_limit

    await db.commit()
    return {"connector_limit": payload.connector_limit, "users_limit": payload.users_limit}


@router.patch(
    "/tenants/{tenant_id}/plan",
    summary="Changer le plan d'un tenant",
    description="Modifie le plan (starter/professional/enterprise) et les quotas associés.",
    responses={200: {"description": "Plan mis à jour"}, 401: _401, 403: _403, 404: _404_tenant},
)
async def update_plan(
    tenant_id: uuid.UUID,
    payload: PlanUpdate,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    VALID_PLANS = {"starter", "professional", "enterprise"}
    if payload.plan not in VALID_PLANS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Invalid plan. Must be one of: {', '.join(sorted(VALID_PLANS))}")
    tenant = await _get_tenant_or_404(tenant_id, db)
    sub = (await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant.id)
    )).scalar_one_or_none()

    if sub is None:
        sub = Subscription(
            tenant_id=tenant.id,
            plan=payload.plan,
            status="active",
            connector_limit=payload.connector_limit,
            users_limit=payload.users_limit,
        )
        db.add(sub)
    else:
        sub.plan = payload.plan
        if payload.connector_limit is not None:
            sub.connector_limit = payload.connector_limit
        if payload.users_limit is not None:
            sub.users_limit = payload.users_limit

    await db.commit()
    return {"plan": payload.plan, "connector_limit": sub.connector_limit, "users_limit": sub.users_limit}


@router.patch(
    "/tenants/{tenant_id}/reactivate",
    status_code=status.HTTP_200_OK,
    summary="Réactiver un tenant",
    description="Réactive tous les utilisateurs du tenant.",
    responses={200: {"description": "Tenant réactivé"}, 401: _401, 403: _403, 404: _404_tenant},
)
async def reactivate_tenant(
    tenant_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant = await _get_tenant_or_404(tenant_id, db)
    users = (await db.execute(
        select(User).where(User.tenant_id == tenant.id)
    )).scalars().all()
    for user in users:
        user.is_active = True
    await db.commit()
    return {"reactivated": len(users)}


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désactiver un tenant",
    description="Désactive tous les utilisateurs du tenant (soft delete). Les données sont conservées.",
    responses={204: {"description": "Tenant désactivé"}, 401: _401, 403: _403, 404: _404_tenant},
)
async def deactivate_tenant(
    tenant_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    tenant = await _get_tenant_or_404(tenant_id, db)
    users = (await db.execute(
        select(User).where(User.tenant_id == tenant.id)
    )).scalars().all()
    for user in users:
        user.is_active = False
    await db.commit()


@router.get(
    "/users",
    response_model=list[AdminUserRead],
    summary="Tous les utilisateurs",
    description="Retourne l'ensemble des utilisateurs de la plateforme avec leur tenant.",
    responses={200: {"description": "Liste de tous les utilisateurs"}, 401: _401, 403: _403},
)
async def list_all_users(
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserRead]:
    users = (await db.execute(select(User))).scalars().all()
    result: list[AdminUserRead] = []
    for user in users:
        tenant_name: str | None = None
        if user.tenant_id:
            tenant = (await db.execute(
                select(Tenant).where(Tenant.id == user.tenant_id)
            )).scalar_one_or_none()
            tenant_name = tenant.name if tenant else None
        result.append(AdminUserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            tenant_id=user.tenant_id,
            tenant_name=tenant_name,
            created_at=user.created_at,
        ))
    return result


@router.patch(
    "/users/{user_id}/role",
    summary="Changer le rôle d'un utilisateur",
    description="Modifie le rôle d'un utilisateur sur toute la plateforme.",
    responses={
        200: {"description": "Rôle mis à jour"},
        401: _401,
        403: _403,
        404: _404_user,
        422: {"description": "Rôle invalide"},
    },
)
async def update_user_role(
    user_id: uuid.UUID,
    payload: RoleUpdate,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = payload.role
    await db.commit()
    return {"id": str(user_id), "role": payload.role}


@router.patch(
    "/users/{user_id}/activate",
    summary="Activer / désactiver un utilisateur",
    description="Bascule l'état actif/inactif d'un utilisateur sur toute la plateforme.",
    responses={
        200: {"description": "État mis à jour"},
        401: _401,
        403: _403,
        404: _404_user,
    },
)
async def toggle_user_active(
    user_id: uuid.UUID,
    payload: ActivateUpdate,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = payload.is_active
    await db.commit()
    return {"id": str(user_id), "is_active": payload.is_active}


@router.post(
    "/impersonate/{user_id}",
    response_model=ImpersonateResponse,
    summary="Impersonner un utilisateur",
    description=(
        "Génère un access token de **1 heure** valide pour l'utilisateur cible. "
        "Permet de se connecter en tant que cet utilisateur pour du support ou du débogage. "
        "Il est impossible d'impersonner un autre `super_admin`."
    ),
    responses={
        200: {"description": "Token d'impersonation (1h)"},
        401: _401,
        403: {"description": "Impossible d'impersonner un super_admin"},
        404: _404_user,
    },
)
async def impersonate_user(
    user_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> ImpersonateResponse:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Cannot impersonate another super admin")

    token = create_access_token(str(user.id), expire_minutes=60)
    return ImpersonateResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        expires_in=3600,
    )
