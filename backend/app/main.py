import time
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy import select, text

from app.api.v1 import admin, admin_licenses, api_keys, auth, billing, connectors, executions, logs, scim, scheduled_jobs, sso, team, webhooks
from app.core.config import settings
from app.core.redis import _get_pool
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User

_START_TIME = time.time()

_TAGS_METADATA = [
    {"name": "auth", "description": "Inscription, connexion, tokens JWT, gestion du profil"},
    {"name": "connectors", "description": "CRUD connecteurs SOAP et REST — création, modification, exécution"},
    {"name": "executions", "description": "Historique et détail des exécutions"},
    {"name": "logs", "description": "Métriques, exécutions récentes, erreurs, alertes"},
    {"name": "api-keys", "description": "Clés d'authentification pour vos applications (préfixe `bxc_`)"},
    {"name": "team", "description": "Gestion des membres du tenant (Admin uniquement)"},
    {"name": "admin", "description": "Gestion des tenants et utilisateurs (Super Admin uniquement)"},
    {"name": "billing", "description": "Licensing enterprise — quotas, usage, factures Stripe"},
    {"name": "health", "description": "Statut de la plateforme"},
    {"name": "sso", "description": "SSO Enterprise — config SAML/OIDC, ACS, tokens SCIM"},
    {"name": "scim", "description": "SCIM 2.0 — provisioning automatique via Azure AD / Okta"},
    {"name": "scheduled-jobs", "description": "Exécutions automatiques planifiées (cron ou interval)"},
    {"name": "webhooks", "description": "Endpoints de notification après chaque exécution — livrés avec signature HMAC"},
]

_DESCRIPTION = """
## API Bridge — Legacy Connector Platform

Connectez vos systèmes SOAP/XML legacy à vos applications modernes via des endpoints REST/JSON \
propres, sécurisés et documentés.

### Authentification

Deux méthodes sont supportées sur les endpoints `/execute` :

| Méthode | Header | Usage |
|---------|--------|-------|
| **JWT Bearer** | `Authorization: Bearer {token}` | Dashboard et intégrations internes |
| **X-API-Key** | `X-API-Key: bxc_...` | Applications et scripts externes |

Pour les endpoints CRUD, seul le **JWT Bearer** est accepté. \
Cliquez sur **Authorize** (🔓) en haut à droite pour vous authentifier.

### Rate Limiting

- API Keys : configurable par clé (défaut 1 000 req/h)
- Réponse `429 Too Many Requests` si quota dépassé

### Codes de retour standards

| Code | Signification |
|------|---------------|
| 200 | Succès |
| 201 | Ressource créée |
| 204 | Succès sans contenu |
| 400 | Requête invalide |
| 401 | Non authentifié |
| 403 | Accès refusé ou quota atteint |
| 404 | Ressource introuvable |
| 409 | Conflit (ex : email déjà utilisé) |
| 422 | Validation du corps échouée |
| 429 | Rate limit dépassé |
| 502 | Service tiers injoignable |
| 504 | Timeout du service tiers |
"""

app = FastAPI(
    title="bxChange API",
    description=_DESCRIPTION,
    version="1.0.0",
    contact={"name": "bxChange Support", "email": "support@bxchange.io"},
    license_info={"name": "Propriétaire — Usage client uniquement"},
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)


def _custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        contact=app.contact,
        license_info=app.license_info,
        tags=_TAGS_METADATA,
        routes=app.routes,
    )
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token obtenu via `POST /api/v1/auth/login`",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Clé API créée dans le dashboard bxChange (préfixe `bxc_`)",
        },
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(connectors.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(api_keys.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(team.router, prefix="/api/v1")
app.include_router(sso.router, prefix="/api/v1")
app.include_router(scim.router, prefix="/api/v1")
app.include_router(scheduled_jobs.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(admin_licenses.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")


@app.on_event("startup")
async def _create_super_admin() -> None:
    """Bootstrap the first super_admin from env vars if none exists."""
    if not settings.super_admin_email or not settings.super_admin_password:
        return
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(User).where(User.role == "super_admin")
        )).scalar_one_or_none()
        if existing is None:
            sa = User(
                email=settings.super_admin_email,
                hashed_password=hash_password(settings.super_admin_password),
                full_name="Super Admin",
                tenant_id=None,
                role="super_admin",
            )
            db.add(sa)
            await db.commit()


@app.get(
    "/health",
    tags=["health"],
    summary="Statut de la plateforme",
    description="Vérifie la connectivité avec la base de données et Redis. Accessible sans authentification.",
    responses={
        200: {"description": "Plateforme opérationnelle"},
    },
)
async def health_check() -> dict:
    db_status = "disconnected"
    redis_status = "disconnected"

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        pass

    try:
        redis = _get_pool()
        await redis.ping()
        redis_status = "connected"
    except Exception:
        pass

    return {
        "status": "ok",
        "version": "1.0.0",
        "database": db_status,
        "redis": redis_status,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - _START_TIME),
    }
