"""Unit tests for snippet_generator service."""
import pytest
from app.services.snippet_generator import (
    _to_camel,
    _to_pascal,
    _to_snake,
    generate_snippet,
    SUPPORTED_LANGS,
)

_ID = "12345678-1234-1234-1234-123456789abc"
_NAME = "Mon Connecteur SOAP"


# ── Naming helpers ─────────────────────────────────────────────────────────────

def test_to_snake_basic():
    assert _to_snake("Mon Connecteur SOAP") == "mon_connecteur_soap"


def test_to_snake_special_chars():
    assert _to_snake("My-Cool API (v2)") == "my_cool_api_v2"


def test_to_snake_empty():
    assert _to_snake("") == "connector"


def test_to_camel_basic():
    assert _to_camel("Mon Connecteur SOAP") == "monConnecteurSoap"


def test_to_camel_single_word():
    assert _to_camel("connector") == "connector"


def test_to_pascal_basic():
    assert _to_pascal("Mon Connecteur SOAP") == "MonConnecteurSoap"


def test_to_pascal_empty():
    assert _to_pascal("") == "Connector"


# ── Snippet content — per language ─────────────────────────────────────────────

def test_curl_snippet_contains_url_and_key():
    s = generate_snippet(_ID, _NAME, "curl", None)
    assert f"/connectors/{_ID}/execute" in s
    assert "X-API-Key: YOUR_API_KEY" in s
    assert "curl -X POST" in s


def test_python_snippet_structure():
    s = generate_snippet(_ID, _NAME, "python", None)
    assert "import httpx" in s
    assert "import asyncio" in s
    assert "async def call_mon_connecteur_soap" in s
    assert f'"{_ID}/execute"' in s or f"/{_ID}/execute" in s
    assert "asyncio.run(" in s


def test_javascript_snippet_structure():
    s = generate_snippet(_ID, _NAME, "javascript", None)
    assert "async function callMonConnecteurSoap" in s
    assert "await fetch(" in s
    assert "JSON.stringify(params)" in s
    assert "X-API-Key" in s


def test_php_snippet_structure():
    s = generate_snippet(_ID, _NAME, "php", None)
    assert "<?php" in s
    assert "function call_mon_connecteur_soap" in s
    assert "curl_init(" in s
    assert "CURLOPT_POST" in s


def test_java_snippet_structure():
    s = generate_snippet(_ID, _NAME, "java", None)
    assert "public class MonConnecteurSoapClient" in s
    assert "HttpRequest.newBuilder()" in s
    assert "X-API-Key" in s
    assert f'"{_ID}/execute"' in s or f"/{_ID}/execute" in s


# ── API key hint ───────────────────────────────────────────────────────────────

def test_api_key_hint_replaces_placeholder():
    s = generate_snippet(_ID, _NAME, "curl", "bxc_my_key")
    assert "bxc_my_key" in s
    assert "YOUR_API_KEY" not in s


def test_no_hint_uses_placeholder():
    s = generate_snippet(_ID, _NAME, "python", None)
    assert "YOUR_API_KEY" in s


# ── Unsupported language ───────────────────────────────────────────────────────

def test_unsupported_lang_raises():
    with pytest.raises(ValueError, match="Unsupported language"):
        generate_snippet(_ID, _NAME, "ruby", None)


# ── All supported languages produce non-empty output ──────────────────────────

@pytest.mark.parametrize("lang", sorted(SUPPORTED_LANGS))
def test_all_langs_produce_output(lang: str):
    s = generate_snippet(_ID, "Test Connector", lang, "bxc_test_key")
    assert len(s) > 50
    assert f"/{_ID}/execute" in s
    assert "bxc_test_key" in s
