"""
Sprint 3 — SOAP Engine + Crypto tests.
Network tests hit the public calculator WSDL at www.dneonline.com.
"""
import pytest

from app.services import soap_engine
from app.services.crypto import decrypt, encrypt
from app.services.soap_engine import (
    SOAPConnectionError,
    SOAPOperationError,
    WSDLLoadError,
)

CALC_WSDL = "http://www.dneonline.com/calculator.asmx?WSDL"


# ── Crypto ─────────────────────────────────────────────────────────────────────

def test_encrypt_returns_string():
    data = {"username": "admin", "password": "s3cr3t"}
    token = encrypt(data)
    assert isinstance(token, str)
    assert token != str(data)


def test_encrypt_decrypt_roundtrip():
    data = {"username": "admin", "password": "s3cr3t", "nested": {"key": 42}}
    assert decrypt(encrypt(data)) == data


def test_encrypt_different_nonce_each_time():
    data = {"key": "value"}
    assert encrypt(data) != encrypt(data)


def test_decrypt_invalid_token():
    with pytest.raises(ValueError):
        decrypt("not-valid-base64-gcm-data")


# ── SOAP Engine — parse_wsdl ───────────────────────────────────────────────────

async def test_parse_wsdl_operations():
    result = await soap_engine.parse_wsdl(CALC_WSDL)
    assert "operations" in result
    ops = result["operations"]
    for expected in ("Add", "Subtract", "Multiply", "Divide"):
        assert expected in ops, f"Expected operation '{expected}' in WSDL"


async def test_parse_wsdl_input_params():
    result = await soap_engine.parse_wsdl(CALC_WSDL)
    add_op = result["operations"]["Add"]
    assert "input" in add_op
    params = add_op["input"]
    assert "intA" in params
    assert "intB" in params


async def test_parse_wsdl_count():
    result = await soap_engine.parse_wsdl(CALC_WSDL)
    assert result["count"] >= 4


async def test_parse_wsdl_inaccessible():
    with pytest.raises((SOAPConnectionError, WSDLLoadError)):
        await soap_engine.parse_wsdl("http://invalid.nonexistent-host-bxchange.local/svc?WSDL")


# ── SOAP Engine — execute ──────────────────────────────────────────────────────

async def test_execute_add():
    result = await soap_engine.execute(
        wsdl_url=CALC_WSDL,
        operation="Add",
        params={"intA": 3, "intB": 5},
        auth_type="none",
    )
    answer = result.get("result") or result.get("AddResult")
    assert answer == 8


async def test_execute_subtract():
    result = await soap_engine.execute(
        wsdl_url=CALC_WSDL,
        operation="Subtract",
        params={"intA": 10, "intB": 3},
        auth_type="none",
    )
    answer = result.get("result") or result.get("SubtractResult")
    assert answer == 7


async def test_execute_multiply():
    result = await soap_engine.execute(
        wsdl_url=CALC_WSDL,
        operation="Multiply",
        params={"intA": 6, "intB": 7},
        auth_type="none",
    )
    answer = result.get("result") or result.get("MultiplyResult")
    assert answer == 42


async def test_execute_operation_not_found():
    with pytest.raises(SOAPOperationError):
        await soap_engine.execute(
            wsdl_url=CALC_WSDL,
            operation="NonExistentOperation",
            params={},
            auth_type="none",
        )


async def test_execute_wsdl_inaccessible():
    with pytest.raises((SOAPConnectionError, WSDLLoadError)):
        await soap_engine.execute(
            wsdl_url="http://invalid.nonexistent-host-bxchange.local/svc?WSDL",
            operation="Add",
            params={"intA": 1, "intB": 2},
            auth_type="none",
        )


# ── Sprint 16 — Advanced config ────────────────────────────────────────────────

async def test_execute_operation_timeout_raises():
    """asyncio.wait_for must cancel if operation_timeout is exceeded."""
    from unittest.mock import patch, MagicMock
    import asyncio

    async def slow_thread(*_a, **_kw):
        await asyncio.sleep(10)

    with patch("app.services.soap_engine.asyncio.to_thread", side_effect=slow_thread):
        with pytest.raises(soap_engine.SOAPTimeoutError):
            await soap_engine.execute(
                wsdl_url=CALC_WSDL,
                operation="Add",
                params={"intA": 1, "intB": 2},
                auth_type="none",
                advanced_config={"operation_timeout": 1},
            )


def test_parse_soap_advanced_defaults():
    from app.services.soap_engine import _parse_soap_advanced
    cfg = _parse_soap_advanced(None)
    assert cfg["operation_timeout"] == 30
    assert cfg["custom_headers"] == {}
    assert cfg["force_list_paths"] == []
    assert cfg["ws_security"] is None


def test_parse_soap_advanced_custom():
    from app.services.soap_engine import _parse_soap_advanced
    raw = {
        "operation_timeout": 60,
        "custom_headers": {"X-Tenant": "acme"},
        "ws_security": {"type": "username_token", "username": "u", "password": "p"},
        "response_path": "Body.Result",
    }
    cfg = _parse_soap_advanced(raw)
    assert cfg["operation_timeout"] == 60
    assert cfg["custom_headers"] == {"X-Tenant": "acme"}
    assert cfg["ws_security"]["username"] == "u"
    assert cfg["response_path"] == "Body.Result"


def test_build_wsse_none_when_no_config():
    from app.services.soap_engine import _build_wsse
    assert _build_wsse(None) is None
    assert _build_wsse({"type": "certificate"}) is None


def test_build_wsse_username_token():
    from app.services.soap_engine import _build_wsse
    wsse = _build_wsse({"type": "username_token", "username": "user", "password": "pass"})
    assert wsse is not None


def test_apply_response_path_hit():
    from app.services.soap_engine import _apply_response_path
    data = {"Body": {"Result": {"value": 42}}}
    assert _apply_response_path(data, "Body.Result") == {"value": 42}


def test_apply_response_path_miss_returns_original():
    from app.services.soap_engine import _apply_response_path
    data = {"Body": {"Result": 42}}
    result = _apply_response_path(data, "Body.Missing.Key")
    assert result == data


def test_apply_response_path_none_passthrough():
    from app.services.soap_engine import _apply_response_path
    data = {"x": 1}
    assert _apply_response_path(data, None) is data
