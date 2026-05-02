"""CRUD — OAuth2 Clients."""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_developer_or_above
from app.models.oauth2_client import OAuth2Client
from app.models.user import User
from app.schemas.oauth2_client import OAuth2ClientCreate, OAuth2ClientCreated, OAuth2ClientRead, OAuth2ClientUpdate

router = APIRouter(prefix="/oauth2-clients", tags=["oauth2"])

_bcrypt = CryptContext(schemes=["bcrypt"], deprecated="auto")

_401 = {"description": "Non authentifié"}
_403 = {"description": "Accès refusé"}
_404 = {"description": "Client introuvable"}


def _gen_client_id() -> str:
    return "bxc_client_" + secrets.token_urlsafe(12)


def _gen_secret() -> str:
    return "secret_" + secrets.token_urlsafe(32)


async def _get_client(client_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession) -> OAuth2Client:
    client = (await db.execute(
        select(OAuth2Client).where(
            OAuth2Client.id == client_id,
            OAuth2Client.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OAuth2 client not found")
    return client


@router.get(
    "",
    response_model=list[OAuth2ClientRead],
    summary="Lister les clients OAuth2",
    responses={200: {"description": "Liste des clients"}, 401: _401},
)
async def list_clients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OAuth2ClientRead]:
    result = await db.execute(
        select(OAuth2Client).where(OAuth2Client.tenant_id == current_user.tenant_id)
    )
    return [OAuth2ClientRead.model_validate(c) for c in result.scalars().all()]


@router.post(
    "",
    response_model=OAuth2ClientCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un client OAuth2",
    description=(
        "Crée un client OAuth2 Machine-to-Machine. Le `client_secret` est retourné **une seule fois** "
        "à la création. Stockez-le immédiatement — il ne sera plus accessible ensuite."
    ),
    responses={
        201: {"description": "Client créé — secret affiché une seule fois"},
        401: _401,
        403: _403,
    },
)
async def create_client(
    payload: OAuth2ClientCreate,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> OAuth2ClientCreated:
    raw_secret = _gen_secret()
    client = OAuth2Client(
        tenant_id=current_user.tenant_id,
        client_id=_gen_client_id(),
        client_secret_hash=_bcrypt.hash(raw_secret),
        client_secret_preview=raw_secret[:8],
        name=payload.name,
        scopes=payload.scopes,
        token_ttl_seconds=payload.token_ttl_seconds,
        allowed_ips=payload.allowed_ips,
        created_by=current_user.id,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    data = OAuth2ClientRead.model_validate(client).model_dump()
    return OAuth2ClientCreated(**data, client_secret=raw_secret)


@router.get(
    "/{client_id}",
    response_model=OAuth2ClientRead,
    summary="Détail d'un client OAuth2",
    responses={200: {"description": "Détail"}, 401: _401, 404: _404},
)
async def get_client(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OAuth2ClientRead:
    client = await _get_client(client_id, current_user.tenant_id, db)
    return OAuth2ClientRead.model_validate(client)


@router.put(
    "/{client_id}",
    response_model=OAuth2ClientRead,
    summary="Modifier un client OAuth2",
    responses={200: {"description": "Mis à jour"}, 401: _401, 403: _403, 404: _404},
)
async def update_client(
    client_id: uuid.UUID,
    payload: OAuth2ClientUpdate,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> OAuth2ClientRead:
    client = await _get_client(client_id, current_user.tenant_id, db)
    if payload.name is not None:
        client.name = payload.name
    if payload.scopes is not None:
        client.scopes = payload.scopes
    if payload.token_ttl_seconds is not None:
        client.token_ttl_seconds = payload.token_ttl_seconds
    if payload.allowed_ips is not None:
        client.allowed_ips = payload.allowed_ips
    if payload.is_active is not None:
        client.is_active = payload.is_active
    await db.commit()
    await db.refresh(client)
    return OAuth2ClientRead.model_validate(client)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Révoquer un client OAuth2",
    responses={204: {"description": "Révoqué"}, 401: _401, 403: _403, 404: _404},
)
async def delete_client(
    client_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> None:
    client = await _get_client(client_id, current_user.tenant_id, db)
    await db.delete(client)
    await db.commit()


@router.post(
    "/{client_id}/rotate",
    response_model=OAuth2ClientCreated,
    summary="Régénérer le secret d'un client OAuth2",
    description=(
        "Génère un nouveau `client_secret`. L'ancien secret est immédiatement invalidé. "
        "Le nouveau secret est affiché **une seule fois**."
    ),
    responses={
        200: {"description": "Nouveau secret généré — affiché une seule fois"},
        401: _401,
        403: _403,
        404: _404,
    },
)
async def rotate_secret(
    client_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> OAuth2ClientCreated:
    client = await _get_client(client_id, current_user.tenant_id, db)
    raw_secret = _gen_secret()
    client.client_secret_hash = _bcrypt.hash(raw_secret)
    client.client_secret_preview = raw_secret[:8]
    await db.commit()
    await db.refresh(client)
    data = OAuth2ClientRead.model_validate(client).model_dump()
    return OAuth2ClientCreated(**data, client_secret=raw_secret)
