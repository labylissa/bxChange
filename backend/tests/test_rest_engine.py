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


# ── Sprint 16 — Advanced config ────────────────────────────────────────────────

async def test_static_headers_merged():
    with respx.mock:
        route = respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={}))
        await rest_engine.execute(
            base_url=BASE, method="GET", path="/data",
            advanced_config={"headers": {"X-Custom": "abc"}},
        )
    assert route.calls[0].request.headers.get("x-custom") == "abc"


async def test_static_query_params_merged():
    with respx.mock:
        route = respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={}))
        await rest_engine.execute(
            base_url=BASE, method="GET", path="/data",
            advanced_config={"query_params": {"version": "2"}},
        )
    assert "version=2" in str(route.calls[0].request.url)


async def test_configurable_retry_count():
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with respx.mock:
            route = respx.get(BASE + "/data").mock(
                side_effect=[httpx.Response(503)] * 2 + [httpx.Response(200, json={"ok": True})]
            )
            result = await rest_engine.execute(
                base_url=BASE, method="GET", path="/data",
                advanced_config={"retry_count": 3, "retry_on_codes": [503]},
            )
    assert result["status_code"] == 200
    assert route.call_count == 3


async def test_configurable_retry_on_codes():
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with respx.mock:
            route = respx.get(BASE + "/data").mock(
                side_effect=[httpx.Response(429), httpx.Response(200, json={})]
            )
            result = await rest_engine.execute(
                base_url=BASE, method="GET", path="/data",
                advanced_config={"retry_count": 2, "retry_on_codes": [429]},
            )
    assert result["status_code"] == 200
    assert mock_sleep.await_count == 1


async def test_body_template_substitution():
    with respx.mock:
        route = respx.post(BASE + "/items").mock(return_value=httpx.Response(201, json={"id": 1}))
        await rest_engine.execute(
            base_url=BASE, method="POST", path="/items",
            params={"name": "widget", "qty": "5"},
            advanced_config={"body_template": '{"name": "{name}", "quantity": {qty}}'},
        )
    sent = route.calls[0].request.content
    assert b"widget" in sent
    assert b"5" in sent


async def test_body_template_missing_variable_raises_400():
    with respx.mock:
        respx.post(BASE + "/items").mock(return_value=httpx.Response(201, json={}))
        with pytest.raises(RESTResponseError) as exc_info:
            await rest_engine.execute(
                base_url=BASE, method="POST", path="/items",
                params={},
                advanced_config={"body_template": '{"name": "{name}"}'},
            )
    assert exc_info.value.status_code == 400


async def test_jsonpath_response_path():
    with respx.mock:
        respx.get(BASE + "/data").mock(
            return_value=httpx.Response(200, json={"data": {"items": [1, 2, 3]}})
        )
        result = await rest_engine.execute(
            base_url=BASE, method="GET", path="/data",
            advanced_config={"response_path": "$.data.items"},
        )
    assert result["body"] == [1, 2, 3]


async def test_jsonpath_no_match_returns_original():
    with respx.mock:
        respx.get(BASE + "/data").mock(
            return_value=httpx.Response(200, json={"x": 1})
        )
        result = await rest_engine.execute(
            base_url=BASE, method="GET", path="/data",
            advanced_config={"response_path": "$.missing.path"},
        )
    assert result["body"] == {"x": 1}


async def test_oauth2_cc_token_fetched_and_cached():
    from fakeredis import FakeAsyncRedis
    fake_redis = FakeAsyncRedis(decode_responses=True)

    with respx.mock:
        respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 3600})
        )
        respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={"ok": True}))

        result = await rest_engine.execute(
            base_url=BASE, method="GET", path="/data",
            advanced_config={
                "oauth2_client_credentials": {
                    "token_url": "https://auth.example.com/token",
                    "client_id": "cid",
                    "client_secret": "csecret",
                    "token_cache_ttl": 3600,
                }
            },
            connector_id="test-conn-id",
            redis_client=fake_redis,
        )

    assert result["status_code"] == 200
    cached = await fake_redis.get("oauth2:test-conn-id")
    assert cached == "tok123"


async def test_oauth2_cc_uses_cache():
    from fakeredis import FakeAsyncRedis
    fake_redis = FakeAsyncRedis(decode_responses=True)
    await fake_redis.set("oauth2:test-conn-id", "cached_token", ex=3600)

    with respx.mock:
        token_route = respx.post("https://auth.example.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "new_token"})
        )
        api_route = respx.get(BASE + "/data").mock(return_value=httpx.Response(200, json={}))

        await rest_engine.execute(
            base_url=BASE, method="GET", path="/data",
            advanced_config={
                "oauth2_client_credentials": {
                    "token_url": "https://auth.example.com/token",
                    "client_id": "cid",
                    "client_secret": "csecret",
                }
            },
            connector_id="test-conn-id",
            redis_client=fake_redis,
        )

    assert token_route.call_count == 0
    auth_header = api_route.calls[0].request.headers.get("authorization", "")
    assert auth_header == "Bearer cached_token"
