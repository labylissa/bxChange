"""Execution service — runs connectors and persists results."""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import _get_pool as _redis_pool
from app.models.connector import Connector
from app.models.execution import Execution
from app.schemas.execution import ExecutionRead
from app.services import crypto, rest_engine, soap_engine, transformer


class ConnectorNotFoundError(Exception):
    """Raised when the connector does not exist or belongs to another tenant."""


class OperationRequiredError(Exception):
    """Raised when a SOAP execution has no operation in params and none stored on the connector."""


class UnsupportedConnectorTypeError(Exception):
    """Raised for an unknown connector type."""


def _coerce_soap_params(params: dict) -> dict:
    """Convert string values to int/float where possible — zeep needs typed values."""
    coerced: dict = {}
    for k, v in params.items():
        if isinstance(v, str):
            try:
                coerced[k] = int(v)
                continue
            except ValueError:
                pass
            try:
                coerced[k] = float(v)
                continue
            except ValueError:
                pass
        coerced[k] = v
    return coerced


async def execute_connector(
    connector_id: uuid.UUID,
    tenant_id: uuid.UUID,
    params: dict,
    body: dict | None,
    transform_override: dict | None,
    triggered_by: str = "dashboard",
    db: AsyncSession = None,
) -> ExecutionRead:
    """Run a connector and persist the execution record.

    Always returns an ExecutionRead — sets status='error' on engine failures
    so the caller always gets an execution_id back.
    """
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.tenant_id == tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise ConnectorNotFoundError(f"Connector {connector_id} not found")

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

    effective_transform = (
        transform_override if transform_override is not None else connector.transform_config
    )
    request_payload = {"params": params, "body": body}
    call_params = dict(params) if params else {}

    start = time.monotonic()
    status = "success"
    error_msg: str | None = None
    result_data: dict = {}
    http_status: int | None = None

    try:
        if connector.type == "soap":
            operation = call_params.pop("operation", None) or connector.operation or ""
            if not operation:
                raise OperationRequiredError("operation is required for SOAP connectors")
            wsdl_source = connector.wsdl_file_path or connector.wsdl_url
            raw = await soap_engine.execute(
                wsdl_url=wsdl_source,
                operation=operation,
                params=_coerce_soap_params(call_params),
                auth_type=connector.auth_type,
                auth_config=auth_config,
                headers=connector.headers or {},
                advanced_config=connector.advanced_config,
            )
            transform_input = raw
            result_data = raw if isinstance(raw, dict) else {"result": raw}

        elif connector.type == "rest":
            method = call_params.pop("method", "GET")
            path = call_params.pop("path", "")
            try:
                redis = _redis_pool()
            except Exception:
                redis = None
            resp = await rest_engine.execute(
                base_url=connector.base_url,
                method=method,
                path=path,
                params=call_params or None,
                body=body,
                headers=connector.headers or {},
                auth_type=connector.auth_type,
                auth_config=auth_config,
                advanced_config=connector.advanced_config,
                connector_id=str(connector_id),
                redis_client=redis,
            )
            http_status = resp.get("status_code")
            body_data = resp.get("body", {})
            result_data = body_data if isinstance(body_data, dict) else {"body": body_data}
            transform_input = result_data

        else:
            raise UnsupportedConnectorTypeError(f"Unknown connector type: {connector.type}")

        if effective_transform:
            result_data = transformer.transform(transform_input, effective_transform)

    except (ConnectorNotFoundError, OperationRequiredError, UnsupportedConnectorTypeError):
        raise
    except Exception as exc:
        status = "error"
        error_msg = str(exc)

    duration_ms = int((time.monotonic() - start) * 1000)

    execution = Execution(
        connector_id=connector_id,
        status=status,
        duration_ms=duration_ms,
        request_payload=request_payload,
        response_payload=result_data,
        error_message=error_msg,
        http_status=http_status,
        triggered_by=triggered_by,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Dispatch webhooks — best-effort, never blocks the response
    try:
        from app.services import webhook_dispatcher
        await webhook_dispatcher.dispatch(
            execution_id=execution.id,
            connector_id=connector_id,
            connector_name=connector.name,
            tenant_id=tenant_id,
            triggered_by=triggered_by,
            status=status,
            duration_ms=duration_ms,
            result=result_data,
            db=db,
        )
    except Exception:
        pass

    return ExecutionRead.model_validate(execution)
