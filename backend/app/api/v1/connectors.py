import os
import pathlib
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_execute_auth
from app.models.connector import Connector
from app.models.execution import Execution
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.connector import (
    ConnectorCreate,
    ConnectorRead,
    ConnectorUpdate,
    PreviewTransformPayload,
    RestTestPayload,
    SnippetResponse,
    WSDLParseResult,
    WsdlSource,
    WsdlUploadResult,
)
from app.schemas.execution import ExecuteRequest, ExecuteResponse
from app.services import crypto, execution_service, rest_engine, snippet_generator, soap_engine, transformer
from app.services.execution_service import ConnectorNotFoundError, OperationRequiredError
from app.services.rest_engine import RESTConnectionError, RESTResponseError, RESTSSLError, RESTTimeoutError
from app.services.soap_engine import SOAPConnectionError, SOAPTimeoutError, WSDLLoadError

router = APIRouter(prefix="/connectors", tags=["connectors"])

UPLOAD_DIR = pathlib.Path(os.environ.get("WSDL_UPLOAD_DIR", "/app/uploads/wsdl"))
_WSDL_NS = "http://schemas.xmlsoap.org/wsdl/"
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

_401 = {"description": "Token invalide ou expiré"}
_403 = {"description": "Accès refusé ou quota atteint"}
_404 = {"description": "Connecteur introuvable"}
_502 = {"description": "Service tiers injoignable"}
_504 = {"description": "Timeout du service tiers"}


async def _get_connector(
    connector_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Connector:
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.tenant_id == tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    return connector


@router.post(
    "/upload-wsdl",
    response_model=WsdlUploadResult,
    status_code=status.HTTP_200_OK,
    summary="Uploader un fichier WSDL local",
    description=(
        "Reçoit un fichier `.wsdl` ou `.xml` en multipart/form-data, valide son contenu, "
        "le stocke sur le serveur et retourne la liste des opérations disponibles.\n\n"
        "**Validations :**\n"
        "- Extension `.wsdl` ou `.xml` uniquement\n"
        "- Taille maximale : 5 MB\n"
        "- Contenu XML valide\n"
        "- Namespace WSDL `http://schemas.xmlsoap.org/wsdl/` présent\n"
        "- Au moins une opération définie\n\n"
        "Le `wsdl_file_id` retourné doit être passé dans `ConnectorCreate.wsdl_file_id` "
        "avec `wsdl_source=upload`."
    ),
    responses={
        200: {"description": "WSDL valide — opérations listées"},
        400: {"description": "Fichier invalide (non-WSDL, XML malformé, aucune opération)"},
        401: _401,
        413: {"description": "Fichier trop volumineux (limite 5 MB)"},
    },
)
async def upload_wsdl(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> WsdlUploadResult:
    filename = file.filename or "unknown.wsdl"
    ext = pathlib.Path(filename).suffix.lower()
    if ext not in (".wsdl", ".xml"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extension invalide — seuls les fichiers .wsdl et .xml sont acceptés",
        )

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux — limite 5 MB",
        )

    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"XML invalide : {exc}",
        )

    if f"{{{_WSDL_NS}}}" not in root.tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Ce fichier n'est pas une définition WSDL valide "
                "(namespace http://schemas.xmlsoap.org/wsdl/ manquant)"
            ),
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}.wsdl"
    file_path.write_bytes(content)

    wsdl_uri = f"file://{file_path}"
    try:
        parse_result = await soap_engine.parse_wsdl(wsdl_uri)
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"WSDL non parseable par le moteur SOAP : {exc}",
        )

    if not parse_result["operations"]:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le WSDL ne contient aucune opération disponible",
        )

    return WsdlUploadResult(
        wsdl_file_id=file_id,
        wsdl_file_path=wsdl_uri,
        operations=list(parse_result["operations"].keys()),
        filename=filename,
    )


@router.post(
    "",
    response_model=ConnectorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un connecteur",
    description=(
        "Crée un connecteur SOAP ou REST. "
        "Pour SOAP avec `wsdl_source=url` : `wsdl_url` est obligatoire. "
        "Pour SOAP avec `wsdl_source=upload` : `wsdl_file_id` (retourné par `/upload-wsdl`) est obligatoire. "
        "`base_url` est obligatoire pour les connecteurs REST. "
        "La création est bloquée si le quota de connecteurs du plan est atteint (403)."
    ),
    responses={
        201: {"description": "Connecteur créé"},
        401: _401,
        403: {"description": "Quota de connecteurs atteint"},
        422: {"description": "Champ obligatoire manquant"},
    },
)
async def create_connector(
    payload: ConnectorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorRead:
    sub = (await db.execute(
        select(Subscription).where(Subscription.tenant_id == current_user.tenant_id)
    )).scalar_one_or_none()
    if sub and sub.connector_limit is not None:
        count = (await db.execute(
            select(func.count(Connector.id)).where(
                Connector.tenant_id == current_user.tenant_id,
                Connector.status != "disabled",
            )
        )).scalar_one()
        if count >= sub.connector_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Quota atteint : votre plan autorise {sub.connector_limit} connecteurs. "
                    "Contactez votre administrateur."
                ),
            )

    encrypted_auth: dict | None = None
    if payload.auth_config:
        encrypted_auth = {"_enc": crypto.encrypt(payload.auth_config)}

    wsdl_file_path: str | None = None
    if payload.wsdl_source == WsdlSource.upload and payload.wsdl_file_id:
        expected = UPLOAD_DIR / f"{payload.wsdl_file_id}.wsdl"
        if not expected.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fichier WSDL uploadé introuvable — veuillez uploader à nouveau",
            )
        wsdl_file_path = f"file://{expected}"

    connector = Connector(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        type=payload.type.value,
        base_url=payload.base_url,
        wsdl_url=payload.wsdl_url,
        wsdl_source=payload.wsdl_source.value,
        wsdl_file_path=wsdl_file_path,
        operation=payload.operation or None,
        auth_type=payload.auth_type.value,
        auth_config=encrypted_auth,
        headers=payload.headers,
        transform_config=payload.transform_config,
        advanced_config=payload.advanced_config,
        created_by=current_user.id,
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    return ConnectorRead.model_validate(connector)


@router.get(
    "",
    response_model=list[ConnectorRead],
    summary="Lister les connecteurs",
    description="Retourne tous les connecteurs du tenant courant, quel que soit leur statut.",
    responses={200: {"description": "Liste des connecteurs"}, 401: _401},
)
async def list_connectors(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConnectorRead]:
    result = await db.execute(
        select(Connector).where(Connector.tenant_id == current_user.tenant_id)
    )
    connectors = result.scalars().all()
    return [ConnectorRead.model_validate(c) for c in connectors]


@router.get(
    "/{connector_id}",
    response_model=ConnectorRead,
    summary="Détail d'un connecteur",
    description="Retourne la configuration complète d'un connecteur (sans les credentials déchiffrés).",
    responses={200: {"description": "Détail du connecteur"}, 401: _401, 404: _404},
)
async def get_connector(
    connector_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorRead:
    connector = await _get_connector(connector_id, current_user.tenant_id, db)
    return ConnectorRead.model_validate(connector)


@router.put(
    "/{connector_id}",
    response_model=ConnectorRead,
    summary="Modifier un connecteur",
    description="Met à jour un ou plusieurs champs du connecteur. Seuls les champs fournis sont modifiés.",
    responses={200: {"description": "Connecteur mis à jour"}, 401: _401, 404: _404},
)
async def update_connector(
    connector_id: uuid.UUID,
    payload: ConnectorUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorRead:
    connector = await _get_connector(connector_id, current_user.tenant_id, db)

    if payload.name is not None:
        connector.name = payload.name
    if payload.base_url is not None:
        connector.base_url = payload.base_url
    if payload.wsdl_url is not None:
        connector.wsdl_url = payload.wsdl_url
    if payload.operation is not None:
        connector.operation = payload.operation or None
    if payload.auth_type is not None:
        connector.auth_type = payload.auth_type.value
    if payload.auth_config is not None:
        connector.auth_config = {"_enc": crypto.encrypt(payload.auth_config)}
    if payload.headers is not None:
        connector.headers = payload.headers
    if payload.transform_config is not None:
        connector.transform_config = payload.transform_config
    if payload.advanced_config is not None:
        connector.advanced_config = payload.advanced_config
    if payload.status is not None:
        connector.status = payload.status.value

    await db.commit()
    await db.refresh(connector)
    return ConnectorRead.model_validate(connector)


@router.delete(
    "/{connector_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un connecteur",
    description=(
        "Supprime définitivement le connecteur et tout son historique d'exécutions. "
        "Si le connecteur utilise un fichier WSDL local (`wsdl_source=upload`), "
        "le fichier est également supprimé du serveur."
    ),
    responses={204: {"description": "Supprimé"}, 401: _401, 404: _404},
)
async def delete_connector(
    connector_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    connector = await _get_connector(connector_id, current_user.tenant_id, db)

    if connector.wsdl_source == "upload" and connector.wsdl_file_path:
        local_path = pathlib.Path(connector.wsdl_file_path.replace("file://", ""))
        local_path.unlink(missing_ok=True)

    await db.execute(delete(Execution).where(Execution.connector_id == connector_id))
    await db.delete(connector)
    await db.commit()


@router.post(
    "/{connector_id}/execute",
    response_model=ExecuteResponse,
    summary="Exécuter un connecteur",
    description=(
        "Appelle le service tiers configuré et retourne la réponse transformée en JSON. "
        "L'exécution est enregistrée dans l'historique.\n\n"
        "**Authentification acceptée :**\n"
        "- `Authorization: Bearer {jwt_token}`\n"
        "- `X-API-Key: bxc_...`\n\n"
        "**Paramètres :**\n"
        "- `params` : paramètres SOAP ou query string REST\n"
        "- `body` : corps JSON pour les requêtes REST POST/PUT\n"
        "- `transform_override` : règles de transformation temporaires (non sauvegardées)\n\n"
        "**Retry automatique :** 3 tentatives avec backoff sur les erreurs 502/503/504."
    ),
    responses={
        200: {"description": "Exécution réussie — résultat JSON retourné"},
        401: {"description": "Token JWT ou X-API-Key invalide"},
        403: _403,
        404: _404,
        429: {"description": "Rate limit de la clé API dépassé"},
        502: _502,
        504: _504,
    },
)
async def execute_connector(
    connector_id: uuid.UUID,
    payload: ExecuteRequest,
    auth: Annotated[tuple[uuid.UUID, str], Depends(get_execute_auth)],
    db: AsyncSession = Depends(get_db),
) -> ExecuteResponse:
    tenant_id, triggered_by = auth
    try:
        exec_read = await execution_service.execute_connector(
            connector_id=connector_id,
            tenant_id=tenant_id,
            params=dict(payload.params),
            body=payload.body,
            transform_override=payload.transform_override,
            triggered_by=triggered_by,
            db=db,
        )
    except ConnectorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    except OperationRequiredError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="operation is required for SOAP connectors")

    return ExecuteResponse(
        execution_id=exec_read.id,
        status=exec_read.status,
        result=exec_read.response_payload,
        duration_ms=exec_read.duration_ms,
        error_message=exec_read.error_message,
    )


@router.post(
    "/{connector_id}/test-wsdl",
    response_model=WSDLParseResult,
    summary="Analyser le WSDL",
    description=(
        "Charge et analyse le WSDL du connecteur SOAP. Retourne la liste des opérations disponibles. "
        "Fonctionne avec les WSDL URL (`wsdl_source=url`) et les fichiers locaux (`wsdl_source=upload`)."
    ),
    responses={
        200: {"description": "Opérations WSDL listées"},
        400: {"description": "Connecteur non SOAP ou source WSDL absente"},
        401: _401,
        404: _404,
        502: _502,
        504: _504,
    },
)
async def test_wsdl(
    connector_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WSDLParseResult:
    connector = await _get_connector(connector_id, current_user.tenant_id, db)

    if connector.type != "soap":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SOAP connectors support WSDL parsing",
        )

    wsdl_source = connector.wsdl_file_path or connector.wsdl_url
    if not wsdl_source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connector has no WSDL source configured",
        )

    try:
        result = await soap_engine.parse_wsdl(wsdl_source)
    except (SOAPConnectionError, WSDLLoadError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except SOAPTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))

    return WSDLParseResult(**result)


@router.post(
    "/{connector_id}/test-rest",
    summary="Tester un endpoint REST",
    description=(
        "Envoie une requête de test au service REST configuré. "
        "La requête n'est **pas** enregistrée dans l'historique."
    ),
    responses={
        200: {"description": "Réponse du service REST"},
        400: {"description": "Connecteur non REST ou base_url absent"},
        401: _401,
        404: _404,
        502: _502,
        504: _504,
    },
)
async def test_rest(
    connector_id: uuid.UUID,
    payload: RestTestPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    connector = await _get_connector(connector_id, current_user.tenant_id, db)

    if connector.type != "rest":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only REST connectors support test-rest",
        )
    if not connector.base_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connector has no base_url configured",
        )

    auth_config: dict = {}
    if (
        connector.auth_config
        and isinstance(connector.auth_config, dict)
        and "_enc" in connector.auth_config
    ):
        try:
            auth_config = crypto.decrypt(connector.auth_config["_enc"])
        except Exception:
            pass

    try:
        return await rest_engine.execute(
            base_url=connector.base_url,
            method=payload.method,
            path=payload.path,
            params=payload.params,
            body=payload.body,
            headers=connector.headers or {},
            auth_type=connector.auth_type,
            auth_config=auth_config,
        )
    except RESTConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except RESTTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))
    except RESTSSLError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except RESTResponseError as exc:
        return {"status_code": exc.status_code, "body": exc.body, "headers": {}}


@router.get(
    "/{connector_id}/snippet",
    response_model=SnippetResponse,
    summary="Générer un snippet de code",
    description=(
        "Retourne un snippet de code prêt à copier pour intégrer ce connecteur depuis n'importe quel langage.\n\n"
        "**Langues supportées :** `curl`, `python`, `javascript`, `php`, `java`\n\n"
        "Si `api_key_id` est fourni, le snippet utilise le nom de la clé comme placeholder au lieu de `YOUR_API_KEY`."
    ),
    responses={
        200: {"description": "Snippet généré"},
        401: _401,
        404: _404,
        422: {"description": "Langue non supportée"},
    },
)
async def get_snippet(
    connector_id: uuid.UUID,
    lang: str = "curl",
    api_key_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SnippetResponse:
    if lang not in snippet_generator.SUPPORTED_LANGS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"lang must be one of {sorted(snippet_generator.SUPPORTED_LANGS)}",
        )

    connector = await _get_connector(connector_id, current_user.tenant_id, db)

    key_hint: str | None = None
    if api_key_id:
        try:
            from app.models.api_key import ApiKey
            key_uuid = uuid.UUID(api_key_id)
            api_key = (await db.execute(
                select(ApiKey).where(
                    ApiKey.id == key_uuid,
                    ApiKey.tenant_id == current_user.tenant_id,
                    ApiKey.is_active.is_(True),
                )
            )).scalar_one_or_none()
            if api_key:
                slug = re.sub(r'[^a-zA-Z0-9]+', '_', api_key.name).strip('_').lower()
                key_hint = f"bxc_{slug}"
        except (ValueError, Exception):
            pass

    snippet = snippet_generator.generate_snippet(
        connector_id=str(connector.id),
        connector_name=connector.name,
        lang=lang,
        api_key_hint=key_hint,
        connector_operation=connector.operation,
    )

    return SnippetResponse(
        lang=lang,
        connector_id=str(connector.id),
        connector_name=connector.name,
        snippet=snippet,
    )


@router.post(
    "/{connector_id}/preview-transform",
    summary="Prévisualiser la transformation",
    description=(
        "Applique les règles de transformation sur du XML brut fourni et retourne "
        "le JSON résultant étape par étape. Utile pour configurer `transform_config`."
    ),
    responses={
        200: {"description": "Résultat de la transformation avec détail des étapes"},
        401: _401,
        404: _404,
        422: {"description": "XML invalide ou impossible à parser"},
    },
)
async def preview_transform(
    connector_id: uuid.UUID,
    payload: PreviewTransformPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_connector(connector_id, current_user.tenant_id, db)

    try:
        steps = transformer.transform_with_steps(payload.raw_xml, payload.transform_config)
    except transformer.XMLParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return {"result": steps["final"], "steps": steps}
