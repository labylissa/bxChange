import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.connector import Connector
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.admin import QuotaRead
from app.schemas.user import (
    ChangePasswordRequest,
    RefreshRequest,
    Token,
    UpdateProfileRequest,
    UserCreate,
    UserLogin,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_PREFIX = "refresh:"

_401 = {"description": "Token invalide ou expiré"}
_403 = {"description": "Compte désactivé ou accès refusé"}


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
    description=(
        "Crée un nouveau compte utilisateur avec le rôle **admin** et un tenant dédié. "
        "Retourne immédiatement un couple access/refresh token."
    ),
    responses={
        201: {"description": "Compte créé, tokens retournés"},
        409: {"description": "Email déjà utilisé"},
        422: {"description": "Validation échouée (email invalide, champ manquant)"},
    },
)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Token:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    tenant = Tenant(
        name=payload.full_name or payload.email.split("@")[0],
        slug=str(uuid.uuid4()),
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
    )
    db.add(tenant)
    await db.flush()

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        tenant_id=tenant.id,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return await _issue_tokens(str(user.id), redis)


@router.post(
    "/login",
    response_model=Token,
    summary="Connexion",
    description="Authentifie l'utilisateur et retourne un access token (15 min) et un refresh token (7 jours).",
    responses={
        200: {"description": "Connexion réussie, tokens retournés"},
        401: {"description": "Email ou mot de passe incorrect"},
        403: {"description": "Compte désactivé"},
    },
)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Token:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    user.last_login_at = datetime.utcnow()
    await db.commit()

    return await _issue_tokens(str(user.id), redis)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Renouveler les tokens",
    description=(
        "Échange un refresh token valide contre un nouveau couple access/refresh token. "
        "Le refresh token précédent est invalidé (rotation)."
    ),
    responses={
        200: {"description": "Nouveaux tokens retournés"},
        401: {"description": "Refresh token invalide, expiré ou déjà utilisé"},
    },
)
async def refresh(
    payload: RefreshRequest,
    redis: Redis = Depends(get_redis),
) -> Token:
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id: str = data["sub"]
        jti: str = data["jti"]
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    stored = await redis.get(f"{_REFRESH_PREFIX}{jti}")
    if stored != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or invalid"
        )

    await redis.delete(f"{_REFRESH_PREFIX}{jti}")
    return await _issue_tokens(user_id, redis)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Mon profil",
    description="Retourne les informations du compte actuellement authentifié.",
    responses={200: {"description": "Profil utilisateur"}, 401: _401},
)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserRead,
    summary="Modifier le profil",
    description="Met à jour le nom complet et/ou l'email de l'utilisateur connecté.",
    responses={
        200: {"description": "Profil mis à jour"},
        401: _401,
        409: {"description": "Email déjà utilisé par un autre compte"},
    },
)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    if payload.email and payload.email != current_user.email:
        existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        current_user.email = payload.email
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    await db.commit()
    await db.refresh(current_user)
    return UserRead.model_validate(current_user)


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Changer le mot de passe",
    description=(
        "Vérifie le mot de passe actuel puis le remplace par le nouveau. "
        "Le nouveau mot de passe doit faire au moins 8 caractères."
    ),
    responses={
        200: {"description": "Mot de passe mis à jour"},
        400: {"description": "Mot de passe actuel incorrect"},
        401: _401,
        422: {"description": "Nouveau mot de passe trop court (< 8 caractères)"},
    },
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe actuel incorrect")
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le nouveau mot de passe doit faire au moins 8 caractères",
        )
    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return {"message": "Mot de passe mis à jour"}


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer le compte",
    description="Désactive définitivement le compte de l'utilisateur connecté. Les données sont conservées.",
    responses={204: {"description": "Compte désactivé"}, 401: _401},
)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    current_user.is_active = False
    await db.commit()


@router.get(
    "/quota",
    response_model=QuotaRead,
    summary="Quotas du tenant",
    description="Retourne le nombre de connecteurs et d'utilisateurs utilisés vs les limites du plan.",
    responses={200: {"description": "Quotas du tenant"}, 401: _401},
)
async def get_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotaRead:
    sub = (await db.execute(
        select(Subscription).where(Subscription.tenant_id == current_user.tenant_id)
    )).scalar_one_or_none()

    connector_count = (await db.execute(
        select(func.count(Connector.id)).where(
            Connector.tenant_id == current_user.tenant_id,
            Connector.status != "disabled",
        )
    )).scalar_one()

    user_count = (await db.execute(
        select(func.count(User.id)).where(User.tenant_id == current_user.tenant_id)
    )).scalar_one()

    return QuotaRead(
        connector_count=connector_count,
        connector_limit=sub.connector_limit if sub else None,
        user_count=user_count,
        users_limit=sub.users_limit if sub else None,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Déconnexion",
    description="Invalide le refresh token. L'access token expire naturellement au bout de 15 minutes.",
    responses={204: {"description": "Déconnecté"}, 401: _401},
)
async def logout(
    payload: RefreshRequest,
    redis: Redis = Depends(get_redis),
) -> None:
    try:
        data = decode_token(payload.refresh_token)
        jti = data.get("jti")
        if jti:
            await redis.delete(f"{_REFRESH_PREFIX}{jti}")
    except JWTError:
        pass


async def _issue_tokens(user_id: str, redis: Redis) -> Token:
    access_token = create_access_token(user_id)
    refresh_token, jti = create_refresh_token(user_id)
    ttl = settings.refresh_token_expire_days * 86400
    await redis.set(f"{_REFRESH_PREFIX}{jti}", user_id, ex=ttl)
    return Token(access_token=access_token, refresh_token=refresh_token)
