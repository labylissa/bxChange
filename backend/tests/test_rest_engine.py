"""Sprint 4 — REST Engine tests (fully mocked with respx)."""
import base64
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.services import rest_engine
from app.services.rest_engine import (
    RESTConnectionError,
    RESTResponseError,
    RESTTimeoutError,
)

BASE = "https://api.example.com"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _exec(**kw):
    defaults = dict(base_url=BASE, method="GET", path="/data", auth_type="none")
    return rest_engine.execute(**{**defaults, **kw})


# ── Basic request / response ───────────────────────────────────────────────────

async def test_get_simple():
    with respx.mock:
        respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={"id": 1}))
        result = await _exec()
    assert result["status_code"] == 200
    assert result["body"] == {"id": 1}


async def test_post_with_body():
    with respx.mock:
        route = respx.post(BASE + "/items").mock(
            return_value=httpx.Response(201, json={"created": True})
        )
        result = await rest_engine.execute(
            base_url=BASE, method="POST", path="/items", body={"name": "widget"}
        )
    assert result["status_code"] == 201
    assert result["body"]["created"] is True
    sent_body = route.calls[0].request.content
    assert b"widget" in sent_body


async def test_response_headers_forwarded():
    with respx.mock:
        respx.get(BASE + "/data").mock(
            return_value=httpx.Response(200, json={}, headers={"x-request-id": "abc123"})
        )
        result = await _exec()
    assert result["headers"]["x-request-id"] == "abc123"


async def test_non_json_body_returned_as_text():
    with respx.mock:
        respx.get(BASE + "/data").mock(return_value=httpx.Response(200, text="plain text"))
        result = await _exec()
    assert result["body"] == "plain text"


# ── Auth: Basic ───────────────────────────────────────────────────────────────

async def test_auth_basic_header():
    with respx.mock:
        route = respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={}))
        await rest_engine.execute(
            base_url=BASE,
            method="GET",
            path="/data",
            auth_type="basic",
            auth_config={"username": "user", "password": "pass"},
        )
    auth_header = route.calls[0].request.headers.get("authorization", "")
    assert auth_header.startswith("Basic ")
    decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
    assert decoded == "user:pass"


# ── Auth: Bearer ──────────────────────────────────────────────────────────────

async def test_auth_bearer_header():
    with respx.mock:
        route = respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={}))
        await rest_engine.execute(
            base_url=BASE,
            method="GET",
            path="/data",
            auth_type="bearer",
            auth_config={"token": "mytoken123"},
        )
    assert route.calls[0].request.headers["authorization"] == "Bearer mytoken123"


# ── Auth: APIKey (header) ──────────────────────────────────────────────────────

async def test_auth_apikey_header():
    with respx.mock:
        route = respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={}))
        await rest_engine.execute(
            base_url=BASE,
            method="GET",
            path="/data",
            auth_type="apikey",
            auth_config={"in": "header", "name": "X-API-Key", "value": "secret123"},
        )
    assert route.calls[0].request.headers["x-api-key"] == "secret123"


# ── Auth: APIKey (query) ──────────────────────────────────────────────────────

async def test_auth_apikey_query_param():
    with respx.mock:
        route = respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={}))
        await rest_engine.execute(
            base_url=BASE,
            method="GET",
            path="/data",
            auth_type="apikey",
            auth_config={"in": "query", "name": "api_key", "value": "qsecret"},
        )
    request_url = str(route.calls[0].request.url)
    assert "api_key=qsecret" in request_url


# ── Retry logic ───────────────────────────────────────────────────────────────

async def test_retry_on_503_exhausts_three_attempts():
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with respx.mock:
            route = respx.get(BASE + "/data").mock(
                side_effect=[
                    httpx.Response(503, json={"error": "unavailable"}),
                    httpx.Response(503, json={"error": "unavailable"}),
                    httpx.Response(503, json={"error": "unavailable"}),
                ]
            )
            with pytest.raises(RESTResponseError) as exc_info:
                await _exec()

    assert exc_info.value.status_code == 503
    assert route.call_count == 3
    # sleep between attempt 0→1 and 1→2
    assert mock_sleep.await_count == 2
    assert mock_sleep.await_args_list[0].args[0] == pytest.approx(1.0)
    assert mock_sleep.await_args_list[1].args[0] == pytest.approx(2.0)


async def test_retry_succeeds_on_second_attempt():
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with respx.mock:
            route = respx.get(BASE + "/data").mock(
                side_effect=[
                    httpx.Response(503),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            result = await _exec()

    assert result["status_code"] == 200
    assert route.call_count == 2


async def test_no_retry_on_4xx():
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with respx.mock:
            route = respx.get(BASE + "/data").mock(return_value=httpx.Response(404))
            with pytest.raises(RESTResponseError) as exc_info:
                await _exec()

    assert exc_info.value.status_code == 404
    assert route.call_count == 1  # no retry
    assert mock_sleep.await_count == 0


# ── Timeout ───────────────────────────────────────────────────────────────────

async def test_timeout_raises_after_retries():
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with respx.mock:
            respx.get(BASE + "/data").mock(
                side_effect=[
                    httpx.TimeoutException("timed out"),
                    httpx.TimeoutException("timed out"),
                    httpx.TimeoutException("timed out"),
                ]
            )
            with pytest.raises(RESTTimeoutError):
                await _exec(timeout=1)

    assert mock_sleep.await_count == 2


# ── Connection error ──────────────────────────────────────────────────────────

async def test_connection_error_no_retry():
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with respx.mock:
            respx.get(BASE + "/data").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            with pytest.raises(RESTConnectionError):
                await _exec()

    assert mock_sleep.await_count == 0  # connection errors are not retried
