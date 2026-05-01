"""SOAP Engine — zeep-based client wrapping sync calls in a thread pool."""
import asyncio
import logging
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

_log = logging.getLogger(__name__)


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

def _parse_soap_advanced(raw: dict | None) -> dict:
    if not raw:
        return {
            "service_name": None, "port_name": None, "operation_timeout": 30,
            "custom_headers": {}, "ws_security": None,
            "response_path": None, "force_list_paths": [],
        }
    return {
        "service_name": raw.get("service_name"),
        "port_name": raw.get("port_name"),
        "operation_timeout": raw.get("operation_timeout", 30),
        "custom_headers": raw.get("custom_headers") or {},
        "ws_security": raw.get("ws_security"),
        "response_path": raw.get("response_path"),
        "force_list_paths": raw.get("force_list_paths") or [],
    }


def _build_wsse(ws_security: dict | None) -> Any:
    if not ws_security or ws_security.get("type") != "username_token":
        return None
    try:
        from zeep.wsse import UsernameToken
        return UsernameToken(
            username=ws_security.get("username", ""),
            password=ws_security.get("password"),
            use_digest=False,
            timestamp_token=ws_security.get("timestamp", True),
        )
    except Exception:
        return None


def _apply_response_path(data: dict, path: str | None) -> dict:
    if not path:
        return data
    try:
        current: Any = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current[key]
            else:
                _log.warning("response_path '%s' not found in result", path)
                return data
        if isinstance(current, dict):
            return current
        return {"value": current}
    except (KeyError, TypeError):
        _log.warning("response_path '%s' not found in result", path)
        return data


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


def _load_client(
    wsdl_url: str,
    session: Session,
    timeout: int,
    plugins: list | None = None,
    wsse: Any = None,
) -> Client:
    transport = Transport(session=session, timeout=timeout, operation_timeout=timeout)
    zeep_settings = ZeepSettings(strict=False, xml_huge_tree=True)
    try:
        return Client(
            wsdl=wsdl_url,
            transport=transport,
            settings=zeep_settings,
            plugins=plugins or [],
            wsse=wsse,
        )
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
    advanced: dict | None = None,
) -> str | dict:
    adv = _parse_soap_advanced(advanced)
    merged_headers = {**extra_headers, **adv["custom_headers"]}
    session = _build_session(auth_type, auth_config, merged_headers)
    history = HistoryPlugin()
    wsse = _build_wsse(adv["ws_security"])
    client = _load_client(wsdl_url, session, timeout, plugins=[history], wsse=wsse)

    # Bind to specific service/port if configured
    service_proxy = client.service
    if adv["service_name"] or adv["port_name"]:
        try:
            service_proxy = client.bind(adv["service_name"], adv["port_name"])
        except Exception:
            pass

    try:
        service_method = getattr(service_proxy, operation)
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
    advanced_config: dict | None = None,
) -> dict:
    """Execute a SOAP operation and return the serialised response."""
    adv = _parse_soap_advanced(advanced_config)
    op_timeout = adv["operation_timeout"]
    force_list_paths = adv["force_list_paths"]

    coro = asyncio.to_thread(
        _execute_sync,
        wsdl_url,
        operation,
        params,
        auth_type,
        auth_config or {},
        headers or {},
        timeout,
        advanced_config,
    )
    try:
        result = await asyncio.wait_for(coro, timeout=op_timeout)
    except asyncio.TimeoutError:
        raise SOAPTimeoutError(f"Operation '{operation}' timed out after {op_timeout}s")

    # Run through transformer pipeline; force_list_paths flows via transform_config extension
    effective_tc = dict(transform_config) if transform_config else {}
    if force_list_paths:
        effective_tc.setdefault("force_list_paths", force_list_paths)

    if isinstance(result, str):
        final = _transformer.transform(result, effective_tc or None)
    elif effective_tc:
        final = _transformer.transform(result, effective_tc)
    else:
        final = result

    return _apply_response_path(final, adv["response_path"])
