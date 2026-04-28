import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.connector import Connector
from app.models.user import User
from app.schemas.connector import (
    ConnectorCreate,
    ConnectorRead,
    ConnectorUpdate,
    PreviewTransformPayload,
    RestTestPayload,
    WSDLParseResult,
)
from app.schemas.execution import ExecuteRequest, ExecuteResponse
from app.services import crypto, execution_service, rest_engine, soap_engine, transformer
from app.services.execution_service import ConnectorNotFoundError
from app.services.rest_engine import RESTConnectionError, RESTResponseError, RESTSSLError, RESTTimeoutError
from app.services.soap_engine import SOAPConnectionError, SOAPTimeoutError, WSDLLoadError

router = APIRouter(prefix="/connectors", tags=["connectors"])


# ── helpers ────────────────────────────────────────────────────────────────────

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


# ── routes ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ConnectorRead, status_code=status.HTTP_201_CREATED)
async def create_connector(
    payload: ConnectorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorRead:
    encrypted_auth: dict | None = None
    if payload.auth_config:
        encrypted_auth = {"_enc": crypto.encrypt(payload.auth_config)}

    connector = Connector(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        type=payload.type.value,
        base_url=payload.base_url,
        wsdl_url=payload.wsdl_url,
        auth_type=payload.auth_type.value,
        auth_config=encrypted_auth,
        headers=payload.headers,
        transform_config=payload.transform_config,
        created_by=current_user.id,
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    return ConnectorRead.model_validate(connector)


@router.get("/", response_model=list[ConnectorRead])
async def list_connectors(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConnectorRead]:
    result = await db.execute(
        select(Connector).where(Connector.tenant_id == current_user.tenant_id)
    )
    connectors = result.scalars().all()
    return [ConnectorRead.model_validate(c) for c in connectors]


@router.get("/{connector_id}", response_model=ConnectorRead)
async def get_connector(
    connector_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorRead:
    connector = await _get_connector(connector_id, current_user.tenant_id, db)
    return ConnectorRead.model_validate(connector)


@router.put("/{connector_id}", response_model=ConnectorRead)
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
    if payload.auth_type is not None:
        connector.auth_type = payload.auth_type.value
    if payload.auth_config is not None:
        connector.auth_config = {"_enc": crypto.encrypt(payload.auth_config)}
    if payload.headers is not None:
        connector.headers = payload.headers
    if payload.transform_config is not None:
        connector.transform_config = payload.transform_config
    if payload.status is not None:
        connector.status = payload.status.value

    await db.commit()
    await db.refresh(connector)
    return ConnectorRead.model_validate(connector)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    connector = await _get_connector(connector_id, current_user.tenant_id, db)
    await db.delete(connector)
    await db.commit()


@router.post("/{connector_id}/test-wsdl", response_model=WSDLParseResult)
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
    if not connector.wsdl_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connector has no wsdl_url configured",
        )

    try:
        result = await soap_engine.parse_wsdl(connector.wsdl_url)
    except (SOAPConnectionError, WSDLLoadError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except SOAPTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))

    return WSDLParseResult(**result)


@router.post("/{connector_id}/test-rest")
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
        # Return remote error as-is — it's informational for a test endpoint
        return {"status_code": exc.status_code, "body": exc.body, "headers": {}}


@router.post("/{connector_id}/execute", response_model=ExecuteResponse)
async def execute_connector(
    connector_id: uuid.UUID,
    payload: ExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecuteResponse:
    try:
        exec_read = await execution_service.execute_connector(
            connector_id=connector_id,
            tenant_id=current_user.tenant_id,
            params=dict(payload.params),
            body=payload.body,
            transform_override=payload.transform_override,
            triggered_by="dashboard",
            db=db,
        )
    except ConnectorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    return ExecuteResponse(
        execution_id=exec_read.id,
        status=exec_read.status,
        result=exec_read.response_payload,
        duration_ms=exec_read.duration_ms,
    )


@router.post("/{connector_id}/preview-transform")
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
