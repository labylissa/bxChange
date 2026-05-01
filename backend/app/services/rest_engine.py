"""REST Engine — async httpx client with typed auth, configurable retry, and advanced features."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

_log = logging.getLogger(__name__)

RETRIABLE_STATUS = frozenset({502, 503, 504})
MAX_RETRIES = 3
BACKOFF_BASE = 1.0


# ── Exceptions ─────────────────────────────────────────────────────────────────

class RESTConnectionError(Exception):
    """Remote host is unreachable."""


class RESTTimeoutError(Exception):
    """Request exceeded the configured timeout."""


class RESTSSLError(Exception):
    """SSL/TLS certificate error."""


class RESTResponseError(Exception):
    """HTTP error after exhausting retries or non-retriable 4xx/5xx."""

    def __init__(self, status_code: int, body: str, message: str = "") -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(message or f"HTTP {status_code}")


# ── Advanced config helpers ─────────────────────────────────────────────────────

def _parse_rest_advanced(raw: dict | None) -> dict:
    if not raw:
        return {
            "headers": {}, "query_params": {},
            "retry_count": MAX_RETRIES, "retry_backoff": BACKOFF_BASE,
            "retry_on_codes": list(RETRIABLE_STATUS),
            "response_path": None, "body_template": None,
            "oauth2_client_credentials": None,
        }
    return {
        "headers": raw.get("headers") or {},
        "query_params": raw.get("query_params") or {},
        "retry_count": raw.get("retry_count", MAX_RETRIES),
        "retry_backoff": raw.get("retry_backoff", BACKOFF_BASE),
        "retry_on_codes": raw.get("retry_on_codes") or list(RETRIABLE_STATUS),
        "response_path": raw.get("response_path"),
        "body_template": raw.get("body_template"),
        "oauth2_client_credentials": raw.get("oauth2_client_credentials"),
    }


# ── Auth builder ───────────────────────────────────────────────────────────────

def _build_auth(
    auth_type: str, auth_config: dict
) -> tuple[httpx.Auth | None, dict, dict]:
    """Return (httpx_auth, extra_headers, extra_query_params)."""
    match auth_type:
        case "basic":
            return (
                httpx.BasicAuth(
                    auth_config.get("username", ""),
                    auth_config.get("password", ""),
                ),
                {},
                {},
            )
        case "bearer":
            return None, {"Authorization": f"Bearer {auth_config.get('token', '')}"}, {}
        case "apikey":
            name = auth_config.get("name", "X-API-Key")
            value = auth_config.get("value", "")
            if auth_config.get("in", "header") == "query":
                return None, {}, {name: value}
            return None, {name: value}, {}
        case _:
            return None, {}, {}


# ── OAuth2 Client Credentials ──────────────────────────────────────────────────

async def _fetch_oauth2_token(
    oauth2_cfg: dict,
    connector_id: str | None,
    redis_client: Any | None,
) -> str:
    cache_key = f"oauth2:{connector_id}" if connector_id else None
    ttl = oauth2_cfg.get("token_cache_ttl", 3600)

    if cache_key and redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return cached
        except Exception:
            pass

    async with httpx.AsyncClient(timeout=30) as client:
        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": oauth2_cfg.get("client_id", ""),
            "client_secret": oauth2_cfg.get("client_secret", ""),
        }
        if oauth2_cfg.get("scope"):
            data["scope"] = oauth2_cfg["scope"]
        resp = await client.post(oauth2_cfg["token_url"], data=data)
        resp.raise_for_status()
        token = resp.json().get("access_token", "")

    if cache_key and redis_client and token:
        try:
            await redis_client.set(cache_key, token, ex=ttl)
        except Exception:
            pass

    return token


# ── JSONPath response extraction ───────────────────────────────────────────────

def _apply_jsonpath(body: Any, path: str) -> Any:
    try:
        from jsonpath_ng import parse as jsonpath_parse
        expr = jsonpath_parse(path)
        matches = [m.value for m in expr.find(body)]
        if not matches:
            _log.warning("response_path '%s' matched nothing", path)
            return body
        return matches[0] if len(matches) == 1 else matches
    except Exception as exc:
        _log.warning("response_path '%s' error: %s", path, exc)
        return body


# ── Response parsing ───────────────────────────────────────────────────────────

def _build_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    return (base + "/" + path.lstrip("/")) if path else base


def _parse_response(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except Exception:
        body = response.text
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body,
    }


# ── Public async API ───────────────────────────────────────────────────────────

async def execute(
    base_url: str,
    method: str,
    path: str = "",
    params: dict | None = None,
    body: dict | None = None,
    headers: dict | None = None,
    auth_type: str = "none",
    auth_config: dict | None = None,
    timeout: int = 30,
    advanced_config: dict | None = None,
    connector_id: str | None = None,
    redis_client: Any | None = None,
) -> dict:
    adv = _parse_rest_advanced(advanced_config)
    retry_count: int = adv["retry_count"]
    retry_backoff: float = adv["retry_backoff"]
    retriable: frozenset[int] = frozenset(adv["retry_on_codes"])

    # Body template substitution — uses {var} syntax, safe with JSON braces like {"key": ...}
    actual_body = body
    if adv["body_template"]:
        missing: list[str] = []

        def _replacer(m: re.Match) -> str:
            key = m.group(1)
            if params and key in params:
                return str(params[key])
            missing.append(key)
            return m.group(0)

        rendered = re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', _replacer, adv["body_template"])
        if missing:
            raise RESTResponseError(400, "", f"body_template missing variables: {missing}")
        try:
            actual_body = json.loads(rendered)
        except (json.JSONDecodeError, ValueError) as exc:
            raise RESTResponseError(400, "", f"body_template produced invalid JSON: {exc}") from exc

    # OAuth2 CC token
    oauth2_bearer: str | None = None
    if adv["oauth2_client_credentials"]:
        try:
            oauth2_bearer = await _fetch_oauth2_token(
                adv["oauth2_client_credentials"], connector_id, redis_client
            )
        except Exception as exc:
            raise RESTConnectionError(f"OAuth2 token fetch failed: {exc}") from exc

    auth, auth_headers, auth_params = _build_auth(auth_type, auth_config or {})

    # Static headers from advanced config have lower priority than per-request headers
    merged_headers = {**adv["headers"], **(headers or {}), **auth_headers}
    if oauth2_bearer:
        merged_headers["Authorization"] = f"Bearer {oauth2_bearer}"

    merged_params = ({**adv["query_params"], **(params or {}), **auth_params}) or None
    url = _build_url(base_url, path)

    last_response: httpx.Response | None = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(retry_count):
            try:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    params=merged_params,
                    json=actual_body,
                    headers=merged_headers,
                    auth=auth,
                )

                if response.status_code in retriable and attempt < retry_count - 1:
                    last_response = response
                    await asyncio.sleep(retry_backoff * (2**attempt))
                    continue

                last_response = response
                break

            except httpx.TimeoutException as exc:
                if attempt < retry_count - 1:
                    await asyncio.sleep(retry_backoff * (2**attempt))
                    continue
                raise RESTTimeoutError(
                    f"Request to {url} timed out after {timeout}s ({retry_count} attempts)"
                ) from exc

            except httpx.ConnectError as exc:
                cause = exc.__cause__ or exc.__context__
                if cause and "ssl" in type(cause).__name__.lower():
                    raise RESTSSLError(f"SSL error connecting to {url}: {exc}") from exc
                raise RESTConnectionError(f"Cannot connect to {url}: {exc}") from exc

    if last_response is None:
        raise RESTConnectionError(f"No response received from {url}")

    if last_response.status_code in retriable:
        parsed = _parse_response(last_response)
        raise RESTResponseError(
            last_response.status_code,
            str(parsed["body"]),
            f"Service unavailable after {retry_count} attempts (HTTP {last_response.status_code})",
        )

    if last_response.status_code >= 400:
        parsed = _parse_response(last_response)
        raise RESTResponseError(last_response.status_code, str(parsed["body"]))

    result = _parse_response(last_response)

    if adv["response_path"] and isinstance(result.get("body"), (dict, list)):
        result["body"] = _apply_jsonpath(result["body"], adv["response_path"])

    return result
