import hashlib
import hmac
import json
import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_developer_or_above
from app.models.connector import Connector
from app.models.user import User
from app.models.webhook_endpoint import WebhookEndpoint
from app.schemas.webhook_endpoint import WebhookEndpointCreate, WebhookEndpointRead, WebhookEndpointUpdate
from app.services import crypto

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_401 = {"description": "Token invalide ou expiré"}
_403 = {"description": "Accès refusé"}
_404 = {"description": "Webhook introuvable"}


async def _get_webhook(webhook_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession) -> WebhookEndpoint:
    wh = (await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if wh is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return wh


@router.get(
    "",
    response_model=list[WebhookEndpointRead],
    summary="Lister les webhooks",
    responses={200: {"description": "Liste des webhooks"}, 401: _401},
)
async def list_webhooks(
    connector_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookEndpointRead]:
    query = select(WebhookEndpoint).where(WebhookEndpoint.tenant_id == current_user.tenant_id)
    if connector_id:
        query = query.where(WebhookEndpoint.connector_id == connector_id)
    webhooks = (await db.execute(query)).scalars().all()
    return [WebhookEndpointRead.model_validate(w) for w in webhooks]


@router.post(
    "",
    response_model=WebhookEndpointRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un webhook",
    responses={201: {"description": "Webhook créé"}, 401: _401, 403: _403, 404: {"description": "Connecteur introuvable"}, 422: {"description": "Validation échouée (URL non-HTTPS, secret trop court, event invalide)"}},
)
async def create_webhook(
    payload: WebhookEndpointCreate,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointRead:
    connector = (await db.execute(
        select(Connector).where(
            Connector.id == payload.connector_id,
            Connector.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    wh = WebhookEndpoint(
        connector_id=payload.connector_id,
        tenant_id=current_user.tenant_id,
        name=payload.name,
        url=payload.url,
        secret=crypto.encrypt({"secret": payload.secret}),
        events=payload.events,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return WebhookEndpointRead.model_validate(wh)


@router.get(
    "/{webhook_id}",
    response_model=WebhookEndpointRead,
    summary="Détail d'un webhook",
    responses={200: {"description": "Détail"}, 401: _401, 404: _404},
)
async def get_webhook(
    webhook_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointRead:
    wh = await _get_webhook(webhook_id, current_user.tenant_id, db)
    return WebhookEndpointRead.model_validate(wh)


@router.put(
    "/{webhook_id}",
    response_model=WebhookEndpointRead,
    summary="Modifier un webhook",
    responses={200: {"description": "Mis à jour"}, 401: _401, 403: _403, 404: _404},
)
async def update_webhook(
    webhook_id: uuid.UUID,
    payload: WebhookEndpointUpdate,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointRead:
    wh = await _get_webhook(webhook_id, current_user.tenant_id, db)
    if payload.name is not None:
        wh.name = payload.name
    if payload.url is not None:
        wh.url = payload.url
    if payload.secret is not None:
        wh.secret = crypto.encrypt({"secret": payload.secret})
    if payload.events is not None:
        wh.events = payload.events
    if payload.is_active is not None:
        wh.is_active = payload.is_active
    await db.commit()
    await db.refresh(wh)
    return WebhookEndpointRead.model_validate(wh)


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un webhook",
    responses={204: {"description": "Supprimé"}, 401: _401, 403: _403, 404: _404},
)
async def delete_webhook(
    webhook_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> None:
    wh = await _get_webhook(webhook_id, current_user.tenant_id, db)
    await db.delete(wh)
    await db.commit()


@router.post(
    "/{webhook_id}/toggle",
    response_model=WebhookEndpointRead,
    summary="Activer / désactiver un webhook",
    responses={200: {"description": "État modifié"}, 401: _401, 403: _403, 404: _404},
)
async def toggle_webhook(
    webhook_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointRead:
    wh = await _get_webhook(webhook_id, current_user.tenant_id, db)
    wh.is_active = not wh.is_active
    await db.commit()
    await db.refresh(wh)
    return WebhookEndpointRead.model_validate(wh)


@router.post(
    "/{webhook_id}/test",
    summary="Envoyer un payload de test",
    responses={
        200: {"description": "Résultat de la livraison test"},
        401: _401,
        403: _403,
        404: _404,
    },
)
async def test_webhook(
    webhook_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wh = await _get_webhook(webhook_id, current_user.tenant_id, db)

    secret = crypto.decrypt(wh.secret)["secret"]
    test_payload = {
        "event": "test",
        "connector_id": str(wh.connector_id),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    body_bytes = json.dumps(test_payload, ensure_ascii=False, sort_keys=True).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                wh.url,
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-bxChange-Signature": sig,
                    "User-Agent": "bxChange-Webhooks/1.0",
                },
            )
        return {"status_code": resp.status_code, "ok": resp.status_code < 400}
    except httpx.TimeoutException:
        return {"status_code": None, "ok": False, "error": "Timeout (10s)"}
    except Exception as exc:
        return {"status_code": None, "ok": False, "error": str(exc)}
