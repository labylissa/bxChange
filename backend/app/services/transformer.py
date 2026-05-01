"""JSON Transformer — cleans and reshapes SOAP/XML responses into plain dicts."""
from __future__ import annotations

from typing import Any

import xmltodict


# ── Exception ──────────────────────────────────────────────────────────────────

class XMLParseError(Exception):
    """Raised when the XML input cannot be parsed."""


# ── A) Parse ───────────────────────────────────────────────────────────────────

def _parse(raw: str | dict, force_list_paths: list[str] | None = None) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        kwargs: dict = {}
        if force_list_paths:
            kwargs["force_list"] = force_list_paths
        result = xmltodict.parse(raw, **kwargs)
        return result if isinstance(result, dict) else {"result": result}
    except Exception as exc:
        raise XMLParseError(f"Invalid XML: {exc}") from exc


# ── B) SOAP envelope unwrap ────────────────────────────────────────────────────

def _find_key(data: dict, local_name: str) -> str | None:
    """Return the dict key whose local name (after ':') matches local_name."""
    for key in data:
        if key == local_name or (isinstance(key, str) and key.endswith(":" + local_name)):
            return key
    return None


def unwrap_soap(data: dict) -> dict:
    """Strip the SOAP 1.1/1.2 Envelope > Body wrapper, returning the Body content."""
    envelope_key = _find_key(data, "Envelope")
    if envelope_key is None:
        return data

    envelope = data[envelope_key]
    if not isinstance(envelope, dict):
        return data

    body_key = _find_key(envelope, "Body")
    if body_key is None:
        return data

    body = envelope[body_key]
    if not isinstance(body, dict):
        return data

    # Unwrap a single XxxResponse wrapper inside Body (ignore namespace attrs)
    real_keys = {k: v for k, v in body.items() if not k.startswith("@")}
    if len(real_keys) == 1:
        inner = next(iter(real_keys.values()))
        if isinstance(inner, dict):
            return inner

    return body


# ── C) Namespace cleaning ──────────────────────────────────────────────────────

_NS_ATTR_PREFIXES = ("@xmlns", "@xsi:", "@xsd:")


def _is_ns_attr(key: str) -> bool:
    return any(key.startswith(p) for p in _NS_ATTR_PREFIXES)


def _strip_ns(key: str) -> str:
    """'ns2:name' → 'name'; '@id' → '@id'; 'name' → 'name'."""
    if not key.startswith("@") and ":" in key:
        return key.split(":", 1)[1]
    return key


def clean_namespaces(data: Any) -> Any:
    """Recursively remove namespace prefixes and @xmlns/@xsi/@xsd attributes."""
    if isinstance(data, dict):
        result: dict = {}
        for key, value in data.items():
            if _is_ns_attr(key):
                continue
            result[_strip_ns(key)] = clean_namespaces(value)
        return result
    if isinstance(data, list):
        return [clean_namespaces(item) for item in data]
    return data


# ── D) Array normalisation ─────────────────────────────────────────────────────

def normalize_arrays(data: Any, array_keys: frozenset[str] | None = None) -> Any:
    """Force keys listed in array_keys to always be lists.

    Without a schema, repeatable detection cannot be automatic, so the caller
    must supply the list of keys expected to be arrays via transform_config['arrays'].
    """
    if isinstance(data, dict):
        result: dict = {}
        for key, value in data.items():
            normalized = normalize_arrays(value, array_keys)
            if array_keys and key in array_keys and not isinstance(normalized, list):
                normalized = [normalized]
            result[key] = normalized
        return result
    if isinstance(data, list):
        return [normalize_arrays(item, array_keys) for item in data]
    return data


# ── E) Mapping ─────────────────────────────────────────────────────────────────

def apply_mapping(data: dict, config: dict) -> dict:
    """Apply field-level transformations in order: exclude → select → rename → flatten."""
    if not config or not isinstance(data, dict):
        return data

    # exclude
    exclude = set(config.get("exclude", []))
    if exclude:
        data = {k: v for k, v in data.items() if k not in exclude}

    # select
    select: list[str] | None = config.get("select")
    if select:
        data = {k: data[k] for k in select if k in data}

    # rename
    rename: dict[str, str] = config.get("rename", {})
    if rename:
        data = {rename.get(k, k): v for k, v in data.items()}

    # flatten (one level of nesting)
    if config.get("flatten"):
        flat: dict = {}
        for key, value in data.items():
            if isinstance(value, dict):
                flat.update(value)
            else:
                flat[key] = value
        data = flat

    return data


# ── F) Finalize ────────────────────────────────────────────────────────────────

def finalize(data: Any) -> Any:
    """Convert stringly-typed values and remove None entries recursively."""
    if isinstance(data, dict):
        result: dict = {}
        for key, value in data.items():
            converted = finalize(value)
            if converted is not None:
                result[key] = converted
        return result

    if isinstance(data, list):
        return [finalize(item) for item in data if item is not None]

    if isinstance(data, str):
        lower = data.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        # integer
        try:
            return int(data)
        except ValueError:
            pass
        # float
        try:
            return float(data)
        except ValueError:
            pass

    return data


# ── Public API ─────────────────────────────────────────────────────────────────

def transform_with_steps(
    raw: str | dict,
    transform_config: dict | None = None,
) -> dict:
    """Run the full pipeline and return each intermediate step."""
    config = transform_config or {}
    force_list_paths: list[str] = config.get("force_list_paths", [])

    data = _parse(raw, force_list_paths or None)

    after_unwrap = unwrap_soap(data)
    after_clean = clean_namespaces(after_unwrap)

    array_keys = frozenset(config.get("arrays", []))
    after_normalize = normalize_arrays(after_clean, array_keys)

    after_mapping = apply_mapping(after_normalize, config)
    final = finalize(after_mapping)

    return {
        "after_unwrap": after_unwrap,
        "after_clean": after_clean,
        "after_normalize": after_normalize,
        "after_mapping": after_mapping,
        "final": final,
    }


def transform(
    raw: str | dict,
    transform_config: dict | None = None,
) -> dict:
    """Transform raw XML string or dict into a clean Python dict."""
    return transform_with_steps(raw, transform_config)["final"]
