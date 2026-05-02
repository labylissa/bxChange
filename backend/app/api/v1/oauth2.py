"""OAuth2 Client Credentials token endpoint (RFC 6749 §4.4)."""
import ipaddress
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.models.oauth2_client import OAuth2Client
from app.models.tenant import Tenant

router = APIRouter(tags=["oauth2"])

_bcrypt = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_SCOPES = {"execute:connectors", "execute:pipelines", "read:results"}


def _check_ip(client_ip: str | None, allowed_ips: list) -> bool:
    if not allowed_ips:
        return True
    if not client_ip:
        return False
    for entry in allowed_ips:
        try:
            if "/" in entry:
                if ipaddress.ip_address(client_ip) in ipaddress.ip_network(entry, strict=False):
                    return True
            elif client_ip == entry:
                return True
        except ValueError:
            pass
    return False


@router.post(
    "/oauth2/token",
    summary="Obtenir un token OAuth2 (Client Credentials)",
    description=(
        "Endpoint standard OAuth2 Client Credentials (RFC 6749 §4.4).\n\n"
        "```\n"
        "POST /oauth2/token\n"
        "Content-Type: application/x-www-form-urlencoded\n\n"
        "grant_type=client_credentials"
        "&client_id=bxc_client_XXXX"
        "&client_secret=SECRET"
        "&scope=execute:connectors\n"
        "```\n\n"
        "**Scopes disponibles :**\n"
        "- `execute:connectors` — Exécuter des connecteurs\n"
        "- `execute:pipelines` — Exécuter des pipelines\n"
        "- `read:results` — Lire l'historique des exécutions\n\n"
        "Le token retourné s'utilise via `Authorization: Bearer {token}` sur les endpoints `/execute`."
    ),
    responses={
        200: {"description": "Token émis"},
        400: {"description": "grant_type invalide ou scope non autorisé"},
        401: {"description": "Credentials incorrects, client inactif ou IP non autorisée"},
        403: {"description": "Licence du tenant inactive"},
    },
)
async def oauth2_token(
    request: Request,
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str = Form(default="execute:connectors"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported_grant_type",
        )

    client = (await db.execute(
        select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    )).scalar_one_or_none()

    if client is None or not _bcrypt.verify(client_secret, client.client_secret_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_client")

    if not client.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="client_inactive")

    client_ip = request.client.host if request.client else None
    if not _check_ip(client_ip, client.allowed_ips):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ip_not_allowed")

    requested_scopes = set(scope.split()) if scope else set()
    granted_scopes = requested_scopes & set(client.scopes) & VALID_SCOPES
    if not granted_scopes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_scope")

    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == client.tenant_id)
    )).scalar_one_or_none()
    if tenant and tenant.license_status in ("expired", "suspended"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant_license_inactive")

    now = datetime.utcnow()
    payload = {
        "sub": str(client.id),
        "tenant_id": str(client.tenant_id),
        "scopes": list(granted_scopes),
        "type": "oauth2_client",
        "exp": now + timedelta(seconds=client.token_ttl_seconds),
        "iat": now,
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    client.last_used_at = now
    await db.commit()

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": client.token_ttl_seconds,
        "scope": " ".join(sorted(granted_scopes)),
    }
