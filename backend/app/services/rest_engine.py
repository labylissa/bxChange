"""REST Engine — async httpx client with typed auth and exponential-backoff retry."""
import asyncio

import httpx

RETRIABLE_STATUS = frozenset({502, 503, 504})
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds; doubles each attempt: 1s → 2s → 4s


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
) -> dict:
    """Execute an HTTP request, retrying on transient failures.

    Retry policy: up to MAX_RETRIES attempts, exponential backoff (1s, 2s, 4s).
    Retries on: timeout, HTTP 502/503/504.
    No retry on: connection errors, SSL errors, 4xx client errors.
    """
    auth, auth_headers, auth_params = _build_auth(auth_type, auth_config or {})
    url = _build_url(base_url, path)
    merged_headers = {**(headers or {}), **auth_headers}
    merged_params = ({**(params or {}), **auth_params}) or None

    last_response: httpx.Response | None = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    params=merged_params,
                    json=body,
                    headers=merged_headers,
                    auth=auth,
                )

                if response.status_code in RETRIABLE_STATUS and attempt < MAX_RETRIES - 1:
                    last_response = response
                    await asyncio.sleep(BACKOFF_BASE * (2**attempt))
                    continue

                last_response = response
                break

            except httpx.TimeoutException as exc:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE * (2**attempt))
                    continue
                raise RESTTimeoutError(
                    f"Request to {url} timed out after {timeout}s ({MAX_RETRIES} attempts)"
                ) from exc

            except httpx.ConnectError as exc:
                cause = exc.__cause__ or exc.__context__
                if cause and "ssl" in type(cause).__name__.lower():
                    raise RESTSSLError(f"SSL error connecting to {url}: {exc}") from exc
                raise RESTConnectionError(f"Cannot connect to {url}: {exc}") from exc

    if last_response is None:
        raise RESTConnectionError(f"No response received from {url}")

    if last_response.status_code in RETRIABLE_STATUS:
        parsed = _parse_response(last_response)
        raise RESTResponseError(
            last_response.status_code,
            str(parsed["body"]),
            f"Service unavailable after {MAX_RETRIES} attempts (HTTP {last_response.status_code})",
        )

    if last_response.status_code >= 400:
        parsed = _parse_response(last_response)
        raise RESTResponseError(last_response.status_code, str(parsed["body"]))

    return _parse_response(last_response)
