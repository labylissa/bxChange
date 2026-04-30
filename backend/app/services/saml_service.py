"""
SAML 2.0 Service — wraps python3-saml for SP-initiated SSO.

Flow:
  1. /sso/login  → get_redirect_url()  → 302 to IdP
  2. IdP → POST /sso/acs  → process_acs() → JIT provision → issue JWT
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _get_saml_auth():
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        return OneLogin_Saml2_Auth
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="python3-saml is not installed. Rebuild the container with SAML dependencies.",
        )


def _get_saml_settings():
    try:
        from onelogin.saml2.settings import OneLogin_Saml2_Settings
        return OneLogin_Saml2_Settings
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="python3-saml is not installed. Rebuild the container with SAML dependencies.",
        )

from app.core.config import settings
from app.models.user import User
from app.services import crypto

if TYPE_CHECKING:
    from app.models.sso_config import SSOConfig


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_saml_settings(sso_config: SSOConfig) -> dict:
    """Build the python3-saml settings dict from an SSOConfig row."""
    # Decrypt IdP certificate
    idp_cert = ""
    if sso_config.certificate:
        try:
            idp_cert = crypto.decrypt(sso_config.certificate).get("cert", "")
        except Exception:
            pass

    return {
        "strict": True,
        "debug": settings.environment != "production",
        "sp": {
            "entityId": settings.sp_entity_id,
            "assertionConsumerService": {
                "url": settings.sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "x509cert": settings.sp_certificate,
            "privateKey": settings.sp_private_key,
        },
        "idp": {
            "entityId": sso_config.entity_id,
            "singleSignOnService": {
                "url": sso_config.sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": idp_cert,
        },
    }


def _build_saml_request(host: str, https: bool, method: str, query_string: str, post_data: dict) -> dict:
    """Build a pseudo-Flask request object that python3-saml expects."""
    return {
        "https": "on" if https else "off",
        "http_host": host,
        "script_name": "",
        "server_port": "443" if https else "80",
        "get_data": {},
        "post_data": post_data,
        "query_string": query_string,
        "request_uri": "",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_sp_metadata() -> str:
    """Return SP metadata XML using the SP certificate / private key from settings."""
    OneLogin_Saml2_Settings = _get_saml_settings()
    sp_settings = {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": settings.sp_entity_id,
            "assertionConsumerService": {
                "url": settings.sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "x509cert": settings.sp_certificate,
            "privateKey": settings.sp_private_key,
        },
        "idp": {
            "entityId": "",
            "singleSignOnService": {"url": "", "binding": ""},
            "x509cert": "",
        },
    }
    saml_settings = OneLogin_Saml2_Settings(settings=sp_settings, sp_validation_only=True)
    metadata = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SP metadata invalid: {errors}",
        )
    return metadata


def get_redirect_url(sso_config: SSOConfig, return_to: str | None = None) -> str:
    """Return the SAML redirect URL (step 1 of SP-initiated SSO)."""
    OneLogin_Saml2_Auth = _get_saml_auth()
    req = _build_saml_request(
        host="app.bxchange.io",
        https=True,
        method="GET",
        query_string="",
        post_data={},
    )
    saml_settings = _build_saml_settings(sso_config)
    auth = OneLogin_Saml2_Auth(req, old_settings=saml_settings)
    return auth.login(return_to=return_to)


def process_acs(
    sso_config: SSOConfig,
    saml_response: str,
    relay_state: str,
    host: str = "app.bxchange.io",
    https: bool = True,
) -> dict:
    """
    Validate the SAML POST response.

    Returns a dict with: email, name, groups, nameid
    Raises HTTPException on validation failure.
    """
    OneLogin_Saml2_Auth = _get_saml_auth()
    req = _build_saml_request(
        host=host,
        https=https,
        method="POST",
        query_string="",
        post_data={"SAMLResponse": saml_response, "RelayState": relay_state},
    )
    saml_settings = _build_saml_settings(sso_config)
    auth = OneLogin_Saml2_Auth(req, old_settings=saml_settings)
    auth.process_response()

    errors = auth.get_errors()
    if errors:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"SAML validation failed: {errors}",
        )
    if not auth.is_authenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SAML authentication failed",
        )

    mapping = sso_config.attr_mapping or {}
    attrs = auth.get_attributes()

    def _first(key: str, fallback: str = "") -> str:
        val = attrs.get(mapping.get(key, key), [])
        return val[0] if val else fallback

    email = _first("email_attr") or auth.get_nameid() or ""
    name = _first("name_attr")
    groups: list[str] = attrs.get(mapping.get("groups_attr", "groups_attr"), [])

    return {
        "email": email.lower().strip(),
        "name": name,
        "groups": groups,
        "nameid": auth.get_nameid(),
    }


async def jit_provision(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    sso_config: SSOConfig,
    attrs: dict,
) -> User:
    """
    Create or update a user from SAML attributes (JIT provisioning).
    Respects tenant users_limit.
    """
    from app.models.subscription import Subscription  # avoid circular
    from app.models.user import User

    email = attrs["email"]
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SAML response contains no usable email attribute",
        )

    # Determine target role from group mapping
    mapping = sso_config.attr_mapping or {}
    role_mapping: dict[str, str] = mapping.get("role_mapping", {})
    target_role = "viewer"
    for group in attrs.get("groups", []):
        if group in role_mapping:
            target_role = role_mapping[group]
            break

    # Find existing user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        # Update role + name if changed
        updated = False
        if user.role != target_role:
            user.role = target_role
            updated = True
        if attrs.get("name") and user.full_name != attrs["name"]:
            user.full_name = attrs["name"]
            updated = True
        if not user.is_active:
            user.is_active = True
            updated = True
        if updated:
            await db.commit()
            await db.refresh(user)
        return user

    # Create new user — check quota first
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
                detail="Tenant user limit reached — cannot provision SSO user",
            )

    new_user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=_random_unusable_hash(),
        full_name=attrs.get("name") or email.split("@")[0],
        tenant_id=tenant_id,
        role=target_role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


def _random_unusable_hash() -> str:
    """Return a bcrypt-incompatible string so SSO users cannot log in with a password."""
    return "!sso:" + hashlib.sha256(uuid.uuid4().bytes).hexdigest()
