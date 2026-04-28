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
