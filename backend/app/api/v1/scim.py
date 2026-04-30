"""
SCIM 2.0 endpoints — User provisioning for Azure AD / Okta.

Auth: Bearer token matched against scim_tokens table (SHA-256 hash).

Routes:
  GET    /scim/v2/Users            — list users
  POST   /scim/v2/Users            — create user
  GET    /scim/v2/Users/{id}       — get user
  PUT    /scim/v2/Users/{id}       — replace user (full update)
  PATCH  /scim/v2/Users/{id}       — partial update
  DELETE /scim/v2/Users/{id}       — deprovision (soft-delete / deactivate)
  GET    /scim/v2/ServiceProviderConfig — capabilities
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.schemas.scim import (
    SCIMGroupCreate,
    SCIMGroupRead,
    SCIMListResponse,
    SCIMPatchRequest,
    SCIMUserCreate,
    SCIMUserRead,
    SCIMUserUpdate,
)
from app.services.scim_service import (
    create_user,
    delete_user,
    get_scim_tenant,
    get_user,
    list_users,
    patch_user,
    update_user,
)

router = APIRouter(prefix="/scim/v2", tags=["scim"])

_SCIM_CONTENT_TYPE = "application/scim+json"


def _scim_response(data: dict | list, status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status_code, media_type=_SCIM_CONTENT_TYPE)


# ── Service Provider Config ───────────────────────────────────────────────────

@router.get(
    "/ServiceProviderConfig",
    summary="SCIM Service Provider Config",
)
async def service_provider_config() -> JSONResponse:
    config = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter": {"supported": True, "maxResults": 200},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Authentication scheme using the OAuth Bearer Token standard",
                "primary": True,
            }
        ],
    }
    return _scim_response(config)


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/Users", summary="SCIM — Lister les utilisateurs")
async def scim_list_users(
    request: Request,
    filter: str | None = Query(None, alias="filter"),
    startIndex: int = Query(1, ge=1),
    count: int = Query(100, ge=1, le=200),
    tenant_id=Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await list_users(tenant_id, db, request, filter_str=filter, start_index=startIndex, count=count)
    return _scim_response(result.model_dump())


@router.post("/Users", summary="SCIM — Créer un utilisateur", status_code=201)
async def scim_create_user(
    payload: SCIMUserCreate,
    request: Request,
    tenant_id=Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    user = await create_user(payload, tenant_id, db, request)
    return _scim_response(user.model_dump(), status_code=201)


@router.get("/Users/{user_id}", summary="SCIM — Obtenir un utilisateur")
async def scim_get_user(
    user_id: str,
    request: Request,
    tenant_id=Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    user = await get_user(user_id, tenant_id, db, request)
    return _scim_response(user.model_dump())


@router.put("/Users/{user_id}", summary="SCIM — Remplacer un utilisateur")
async def scim_replace_user(
    user_id: str,
    payload: SCIMUserUpdate,
    request: Request,
    tenant_id=Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    user = await update_user(user_id, payload, tenant_id, db, request)
    return _scim_response(user.model_dump())


@router.patch("/Users/{user_id}", summary="SCIM — Modifier un utilisateur")
async def scim_patch_user(
    user_id: str,
    patch: SCIMPatchRequest,
    request: Request,
    tenant_id=Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    user = await patch_user(user_id, patch, tenant_id, db, request)
    return _scim_response(user.model_dump())


@router.delete("/Users/{user_id}", status_code=204, summary="SCIM — Déprovisionner un utilisateur")
async def scim_delete_user(
    user_id: str,
    tenant_id=Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_user(user_id, tenant_id, db)
