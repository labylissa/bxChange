"""
SSO endpoints — SAML 2.0 and OIDC config + login flows + SCIM token management.

Routes:
  POST   /sso/config              — create SSO config (admin)
  GET    /sso/config              — get current SSO config (admin)
  PUT    /sso/config              — update SSO config (admin)
  DELETE /sso/config              — delete SSO config (admin)
  GET    /sso/metadata            — SP metadata XML (public)
  GET    /sso/login               — initiate SAML redirect (public)
  POST   /sso/acs                 — SAML ACS callback (public)
  GET    /sso/oidc/login          — initiate OIDC redirect (public)
  GET    /sso/oidc/callback       — OIDC callback (public)
  GET    /sso/domain-hint/{domain}— check if domain has SSO configured (public)
  GET    /sso/scim-tokens         — list SCIM tokens (admin)
  POST   /sso/scim-tokens         — create SCIM token (admin)
  DELETE /sso/scim-tokens/{id}    — revoke SCIM token (admin)
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_admin_or_above
from app.core.security import create_access_token, create_refresh_token
from app.models.scim_token import ScimToken
from app.models.sso_config import SSOConfig
from app.models.sso_domain_hint import SSODomainHint
from app.models.user import User
from app.schemas.sso import (
    DomainHintRead,
    ScimTokenCreate,
    ScimTokenCreated,
    ScimTokenRead,
    SPMetadata,
    SSOConfigCreate,
    SSOConfigRead,
    SSOConfigUpdate,
)
from app.services import crypto

router = APIRouter(prefix="/sso", tags=["sso"])

_401 = {"description": "Token invalide ou expiré"}
_403 = {"description": "Droits insuffisants"}
_404 = {"description": "Introuvable"}


# ── SSO Config CRUD ───────────────────────────────────────────────────────────

@router.post(
    "/config",
    response_model=SSOConfigRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer la configuration SSO",
    responses={201: {"description": "Config SSO créée"}, 401: _401, 403: _403},
)
async def create_sso_config(
    payload: SSOConfigCreate,
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> SSOConfigRead:
    # Only one config per tenant
    existing = await db.execute(
        select(SSOConfig).where(SSOConfig.tenant_id == current_user.tenant_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SSO config already exists for this tenant. Use PUT to update.",
        )

    encrypted_cert = None
    if payload.certificate:
        encrypted_cert = crypto.encrypt({"cert": payload.certificate})

    sso_config = SSOConfig(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        idp_type=payload.idp_type.value,
        entity_id=payload.entity_id,
        sso_url=payload.sso_url,
        certificate=encrypted_cert,
        attr_mapping=payload.attr_mapping,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(sso_config)
    await db.flush()

    # Create domain hints
    for domain in payload.domains:
        hint = SSODomainHint(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            domain=domain.lower().strip(),
            sso_config_id=sso_config.id,
        )
        db.add(hint)

    await db.commit()
    await db.refresh(sso_config)
    return SSOConfigRead.model_validate(sso_config)


@router.get(
    "/config",
    response_model=SSOConfigRead,
    summary="Obtenir la configuration SSO",
    responses={200: {"description": "Config SSO"}, 401: _401, 403: _403, 404: _404},
)
async def get_sso_config(
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> SSOConfigRead:
    result = await db.execute(
        select(SSOConfig).where(SSOConfig.tenant_id == current_user.tenant_id)
    )
    sso_config = result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SSO config found")
    return SSOConfigRead.model_validate(sso_config)


@router.put(
    "/config",
    response_model=SSOConfigRead,
    summary="Mettre à jour la configuration SSO",
    responses={200: {"description": "Config SSO mise à jour"}, 401: _401, 403: _403, 404: _404},
)
async def update_sso_config(
    payload: SSOConfigUpdate,
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> SSOConfigRead:
    result = await db.execute(
        select(SSOConfig).where(SSOConfig.tenant_id == current_user.tenant_id)
    )
    sso_config = result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SSO config found")

    if payload.entity_id is not None:
        sso_config.entity_id = payload.entity_id
    if payload.sso_url is not None:
        sso_config.sso_url = payload.sso_url
    if payload.certificate is not None:
        sso_config.certificate = crypto.encrypt({"cert": payload.certificate})
    if payload.attr_mapping is not None:
        sso_config.attr_mapping = payload.attr_mapping
    if payload.is_active is not None:
        sso_config.is_active = payload.is_active
    if payload.domains is not None:
        # Replace domain hints
        await db.execute(
            select(SSODomainHint).where(SSODomainHint.sso_config_id == sso_config.id)
        )
        # Delete old hints
        old = await db.execute(
            select(SSODomainHint).where(SSODomainHint.sso_config_id == sso_config.id)
        )
        for hint in old.scalars().all():
            await db.delete(hint)
        # Add new hints
        for domain in payload.domains:
            hint = SSODomainHint(
                id=uuid.uuid4(),
                tenant_id=sso_config.tenant_id,
                domain=domain.lower().strip(),
                sso_config_id=sso_config.id,
            )
            db.add(hint)

    await db.commit()
    await db.refresh(sso_config)
    return SSOConfigRead.model_validate(sso_config)


@router.delete(
    "/config",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer la configuration SSO",
    responses={204: {"description": "Config supprimée"}, 401: _401, 403: _403, 404: _404},
)
async def delete_sso_config(
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(SSOConfig).where(SSOConfig.tenant_id == current_user.tenant_id)
    )
    sso_config = result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SSO config found")
    await db.delete(sso_config)
    await db.commit()


# ── SP Metadata ───────────────────────────────────────────────────────────────

@router.get(
    "/metadata",
    response_class=Response,
    summary="SP Metadata XML (SAML)",
    description="Retourne le SP metadata XML pour configurer l'IdP SAML.",
)
async def sp_metadata() -> Response:
    try:
        from app.services.saml_service import get_sp_metadata
        xml = get_sp_metadata()
        return Response(content=xml, media_type="application/xml")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ── SAML Login / ACS ─────────────────────────────────────────────────────────

@router.get(
    "/login",
    summary="Initier SSO SAML (redirect IdP)",
    description="Redirige l'utilisateur vers l'IdP SAML. Paramètre `domain` permet de sélectionner le tenant.",
)
async def saml_login(
    domain: str = Query(..., description="Email domain (e.g. acme.com)"),
    return_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    from app.services.saml_service import get_redirect_url

    hint = await db.execute(
        select(SSODomainHint).where(SSODomainHint.domain == domain.lower().strip())
    )
    domain_hint = hint.scalar_one_or_none()
    if domain_hint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SSO configured for this domain")

    sso_result = await db.execute(
        select(SSOConfig).where(SSOConfig.id == domain_hint.sso_config_id, SSOConfig.is_active == True)
    )
    sso_config = sso_result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO config not active")

    redirect_url = get_redirect_url(sso_config, return_to=return_to)
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post(
    "/acs",
    summary="SAML ACS — traitement de la réponse IdP",
    description="Endpoint consommé par l'IdP après authentification SAML. Retourne des tokens JWT.",
)
async def saml_acs(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.saml_service import jit_provision, process_acs

    form = await request.form()
    saml_response = form.get("SAMLResponse", "")
    relay_state = form.get("RelayState", "")

    if not saml_response:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing SAMLResponse")

    # Determine the SSO config from relay state (tenant id encoded) or fallback
    # For simplicity, relay_state = tenant_id (set during login)
    tenant_id_str = relay_state
    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid relay state — cannot determine tenant",
        )

    sso_result = await db.execute(
        select(SSOConfig).where(SSOConfig.tenant_id == tenant_id, SSOConfig.is_active == True)
    )
    sso_config = sso_result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO config not found")

    host = request.headers.get("host", "app.bxchange.io")
    https = request.url.scheme == "https"
    attrs = process_acs(sso_config, saml_response, relay_state, host=host, https=https)
    user = await jit_provision(db, tenant_id, sso_config, attrs)

    access_token = create_access_token(str(user.id))
    refresh_token, _ = create_refresh_token(str(user.id))
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ── OIDC Login / Callback ─────────────────────────────────────────────────────

@router.get(
    "/oidc/login",
    summary="Initier SSO OIDC (redirect provider)",
)
async def oidc_login(
    domain: str = Query(..., description="Email domain for tenant lookup"),
    redirect_uri: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.oidc_service import get_authorization_url

    hint = await db.execute(
        select(SSODomainHint).where(SSODomainHint.domain == domain.lower().strip())
    )
    domain_hint = hint.scalar_one_or_none()
    if domain_hint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SSO configured for this domain")

    sso_result = await db.execute(
        select(SSOConfig).where(
            SSOConfig.id == domain_hint.sso_config_id,
            SSOConfig.is_active == True,
            SSOConfig.idp_type == "oidc",
        )
    )
    sso_config = sso_result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC SSO config not active")

    state = str(sso_config.tenant_id)
    auth_url, state = await get_authorization_url(sso_config, redirect_uri, state=state)
    return {"authorization_url": auth_url, "state": state}


@router.get(
    "/oidc/callback",
    summary="Callback OIDC — échange du code + provision JIT",
)
async def oidc_callback(
    code: str = Query(...),
    state: str = Query(...),
    redirect_uri: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.oidc_service import exchange_code
    from app.services.saml_service import jit_provision

    try:
        tenant_id = uuid.UUID(state)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")

    sso_result = await db.execute(
        select(SSOConfig).where(
            SSOConfig.tenant_id == tenant_id,
            SSOConfig.is_active == True,
            SSOConfig.idp_type == "oidc",
        )
    )
    sso_config = sso_result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC SSO config not found")

    attrs = await exchange_code(sso_config, redirect_uri, code, state)
    user = await jit_provision(db, tenant_id, sso_config, attrs)

    access_token = create_access_token(str(user.id))
    refresh_token, _ = create_refresh_token(str(user.id))
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ── Domain Hint ───────────────────────────────────────────────────────────────

@router.get(
    "/domain-hint/{domain}",
    response_model=DomainHintRead,
    summary="Vérifier si un domaine a un SSO configuré",
)
async def domain_hint(
    domain: str,
    db: AsyncSession = Depends(get_db),
) -> DomainHintRead:
    result = await db.execute(
        select(SSODomainHint).where(SSODomainHint.domain == domain.lower().strip())
    )
    hint = result.scalar_one_or_none()
    if hint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SSO for this domain")
    return DomainHintRead.model_validate(hint)


# ── SCIM Token management ─────────────────────────────────────────────────────

@router.get(
    "/scim-tokens",
    response_model=list[ScimTokenRead],
    summary="Lister les tokens SCIM",
    responses={200: {"description": "Liste des tokens SCIM"}, 401: _401, 403: _403},
)
async def list_scim_tokens(
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> list[ScimTokenRead]:
    result = await db.execute(
        select(ScimToken).where(ScimToken.tenant_id == current_user.tenant_id)
    )
    return [ScimTokenRead.model_validate(t) for t in result.scalars().all()]


@router.post(
    "/scim-tokens",
    response_model=ScimTokenCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un token SCIM",
    description=(
        "Génère un token SCIM Bearer. La valeur brute (`raw_token`) est retournée "
        "**une seule fois** — conservez-la en lieu sûr."
    ),
    responses={201: {"description": "Token créé"}, 401: _401, 403: _403},
)
async def create_scim_token(
    payload: ScimTokenCreate,
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> ScimTokenCreated:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    scim_token = ScimToken(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        token_hash=token_hash,
        name=payload.name,
        expires_at=payload.expires_at,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(scim_token)
    await db.commit()
    await db.refresh(scim_token)

    read = ScimTokenRead.model_validate(scim_token)
    return ScimTokenCreated(**read.model_dump(), raw_token=raw_token)


@router.delete(
    "/scim-tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Révoquer un token SCIM",
    responses={204: {"description": "Token révoqué"}, 401: _401, 403: _403, 404: _404},
)
async def revoke_scim_token(
    token_id: uuid.UUID,
    current_user: User = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ScimToken).where(
            ScimToken.id == token_id,
            ScimToken.tenant_id == current_user.tenant_id,
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SCIM token not found")
    token.is_active = False
    await db.commit()
