"""SOAP Engine — zeep-based client wrapping sync calls in a thread pool."""
import asyncio
from typing import Any

from app.services import transformer as _transformer

import requests.exceptions as req_exc
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Settings as ZeepSettings
from zeep.exceptions import Fault
from zeep.helpers import serialize_object
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport

try:
    from lxml import etree as _lxml_etree
except ImportError:
    _lxml_etree = None


# ── Custom exceptions ──────────────────────────────────────────────────────────

class WSDLLoadError(Exception):
    """WSDL is invalid or inaccessible."""


class SOAPFaultError(Exception):
    """Business-level SOAP fault returned by the server."""
    def __init__(self, message: str, code: str = "") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class SOAPOperationError(Exception):
    """Requested operation does not exist in the WSDL."""


class SOAPConnectionError(Exception):
    """Service host is unreachable."""


class SOAPTimeoutError(Exception):
    """Request exceeded the configured timeout."""


# ── Internal sync helpers ──────────────────────────────────────────────────────

def _build_session(auth_type: str, auth_config: dict, extra_headers: dict) -> Session:
    session = Session()
    if extra_headers:
        session.headers.update(extra_headers)

    match auth_type:
        case "basic":
            session.auth = HTTPBasicAuth(
                auth_config.get("username", ""), auth_config.get("password", "")
            )
        case "bearer":
            session.headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
        case "apikey":
            header_name = auth_config.get("header_name", "X-API-Key")
            session.headers[header_name] = auth_config.get("api_key", "")

    return session


def _load_client(wsdl_url: str, session: Session, timeout: int, plugins: list | None = None) -> Client:
    transport = Transport(
        session=session,
        timeout=timeout,
        operation_timeout=timeout,
    )
    zeep_settings = ZeepSettings(strict=False, xml_huge_tree=True)
    try:
        return Client(wsdl=wsdl_url, transport=transport, settings=zeep_settings, plugins=plugins or [])
    except req_exc.ConnectionError as exc:
        raise SOAPConnectionError(f"Cannot connect to WSDL host: {exc}") from exc
    except req_exc.Timeout as exc:
        raise SOAPTimeoutError(f"WSDL download timed out: {exc}") from exc
    except Exception as exc:
        raise WSDLLoadError(f"Invalid or inaccessible WSDL: {exc}") from exc


def _serialize_result(raw: Any) -> dict:
    if raw is None:
        return {}
    serialized = serialize_object(raw)
    if isinstance(serialized, dict):
        return serialized
    return {"result": serialized}


def _get_op_params(operation: Any) -> dict:
    """Best-effort introspection of input elements."""
    params: dict = {}
    try:
        body = operation.input.body
        if body and hasattr(body, "type") and hasattr(body.type, "elements"):
            for elem_name, element in body.type.elements:
                type_name = "any"
                if element.type and hasattr(element.type, "name") and element.type.name:
                    type_name = str(element.type.name)
                params[elem_name] = type_name
    except Exception:
        pass
    return params


# ── Sync implementations (run in thread pool) ──────────────────────────────────

def _parse_wsdl_sync(wsdl_url: str) -> dict:
    session = Session()
    transport = Transport(session=session, timeout=30)
    zeep_settings = ZeepSettings(strict=False, xml_huge_tree=True)
    try:
        client = Client(wsdl=wsdl_url, transport=transport, settings=zeep_settings)
    except req_exc.ConnectionError as exc:
        raise SOAPConnectionError(f"Cannot connect to WSDL host: {exc}") from exc
    except req_exc.Timeout as exc:
        raise SOAPTimeoutError(f"WSDL download timed out: {exc}") from exc
    except Exception as exc:
        raise WSDLLoadError(f"Invalid or inaccessible WSDL: {exc}") from exc

    operations: dict = {}
    for service in client.wsdl.services.values():
        for port in service.ports.values():
            for op_name, operation in port.binding._operations.items():
                operations[op_name] = {"input": _get_op_params(operation)}

    return {"operations": operations, "count": len(operations)}


def _execute_sync(
    wsdl_url: str,
    operation: str,
    params: dict,
    auth_type: str,
    auth_config: dict,
    extra_headers: dict,
    timeout: int,
) -> str | dict:
    session = _build_session(auth_type, auth_config, extra_headers)
    history = HistoryPlugin()
    client = _load_client(wsdl_url, session, timeout, plugins=[history])

    try:
        service_method = getattr(client.service, operation)
    except AttributeError:
        try:
            port = next(iter(next(iter(client.wsdl.services.values())).ports.values()))
            available = list(port.binding._operations.keys())
        except Exception:
            available = []
        raise SOAPOperationError(
            f"Operation '{operation}' not found. Available: {available}"
        )

    try:
        raw = service_method(**params)
    except Fault as exc:
        raise SOAPFaultError(str(exc.message), str(exc.code)) from exc
    except req_exc.Timeout as exc:
        raise SOAPTimeoutError(f"Request timed out after {timeout}s") from exc
    except req_exc.ConnectionError as exc:
        raise SOAPConnectionError(f"Connection failed: {exc}") from exc

    # Return raw XML so the transformer uses the same XML tag names as /preview-transform.
    # Without this, zeep's serialize_object produces different key names (e.g. "result"
    # instead of "AddResult"), causing transform_config rules to silently have no effect.
    if _lxml_etree is not None:
        try:
            envelope = history.last_received.get("envelope") if history.last_received else None
            if envelope is not None:
                return _lxml_etree.tostring(envelope, encoding="unicode")
        except Exception:
            pass

    return _serialize_result(raw)


# ── Public async API ───────────────────────────────────────────────────────────

async def parse_wsdl(wsdl_url: str) -> dict:
    """Parse a WSDL and return the list of available operations."""
    return await asyncio.to_thread(_parse_wsdl_sync, wsdl_url)


async def execute(
    wsdl_url: str,
    operation: str,
    params: dict,
    auth_type: str = "none",
    auth_config: dict | None = None,
    headers: dict | None = None,
    timeout: int = 30,
    transform_config: dict | None = None,
) -> dict:
    """Execute a SOAP operation and return the serialised response."""
    result = await asyncio.to_thread(
        _execute_sync,
        wsdl_url,
        operation,
        params,
        auth_type,
        auth_config or {},
        headers or {},
        timeout,
    )
    # When HistoryPlugin captured raw XML, run it through the full transformer pipeline
    # (parse → unwrap envelope → clean namespaces → apply config) so that key names
    # match exactly what /preview-transform produces from the same XML.
    if isinstance(result, str):
        return _transformer.transform(result, transform_config)
    if transform_config is not None:
        return _transformer.transform(result, transform_config)
    return result
