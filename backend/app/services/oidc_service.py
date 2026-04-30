"""
OIDC Service — wraps authlib for OIDC provider integration.

Flow:
  1. /sso/oidc/login  → get_authorization_url()  → 302 to IdP
  2. IdP → GET /sso/oidc/callback  → exchange_code() → JIT provision → issue JWT
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _get_oauth2_client():
    try:
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        return AsyncOAuth2Client
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="authlib is not installed. Rebuild the container with OIDC dependencies.",
        )

from app.services.saml_service import _random_unusable_hash, jit_provision

if TYPE_CHECKING:
    from app.models.sso_config import SSOConfig


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client_secret(sso_config: SSOConfig) -> str:
    """Decrypt the OIDC client_secret stored in certificate field."""
    if not sso_config.certificate:
        return ""
    try:
        from app.services import crypto
        return crypto.decrypt(sso_config.certificate).get("cert", "")
    except Exception:
        return ""


def _get_oidc_mapping(sso_config: SSOConfig) -> dict:
    return sso_config.attr_mapping or {}


# ── Public API ────────────────────────────────────────────────────────────────

async def get_well_known(issuer_url: str) -> dict:
    """Fetch OIDC discovery document from issuer."""
    discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(discovery_url)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch OIDC discovery from {discovery_url}",
            )
        return resp.json()


async def get_authorization_url(
    sso_config: SSOConfig,
    redirect_uri: str,
    state: str | None = None,
) -> tuple[str, str]:
    """
    Return (authorization_url, state) for redirect.
    sso_config.sso_url is the OIDC issuer URL.
    sso_config.entity_id is the client_id.
    """
    discovery = await get_well_known(sso_config.sso_url)
    auth_endpoint = discovery["authorization_endpoint"]
    client_secret = _get_client_secret(sso_config)
    AsyncOAuth2Client = _get_oauth2_client()

    client = AsyncOAuth2Client(
        client_id=sso_config.entity_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="openid email profile",
    )
    state = state or secrets.token_urlsafe(16)
    url, state = client.create_authorization_url(auth_endpoint, state=state)
    return url, state


async def exchange_code(
    sso_config: SSOConfig,
    redirect_uri: str,
    code: str,
    state: str,
) -> dict:
    """
    Exchange authorization code for tokens and return normalized user attributes.
    Returns: {email, name, groups, sub}
    """
    discovery = await get_well_known(sso_config.sso_url)
    token_endpoint = discovery["token_endpoint"]
    userinfo_endpoint = discovery.get("userinfo_endpoint", "")
    client_secret = _get_client_secret(sso_config)
    mapping = _get_oidc_mapping(sso_config)
    AsyncOAuth2Client = _get_oauth2_client()

    client = AsyncOAuth2Client(
        client_id=sso_config.entity_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    token = await client.fetch_token(token_endpoint, code=code)

    # Fetch userinfo
    userinfo: dict = {}
    if userinfo_endpoint:
        resp = await client.get(userinfo_endpoint)
        if resp.status_code == 200:
            userinfo = resp.json()

    email_field = mapping.get("email_attr", "email")
    name_field = mapping.get("name_attr", "name")
    groups_field = mapping.get("groups_attr", "groups")

    email = userinfo.get(email_field, "")
    name = userinfo.get(name_field, userinfo.get("name", ""))
    groups = userinfo.get(groups_field, [])
    if isinstance(groups, str):
        groups = [groups]

    return {
        "email": email.lower().strip() if email else "",
        "name": name,
        "groups": groups,
        "sub": userinfo.get("sub", ""),
    }
