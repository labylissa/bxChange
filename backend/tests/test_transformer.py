"""Sprint 5 — JSON Transformer tests."""
import pytest

from app.services.transformer import (
    XMLParseError,
    apply_mapping,
    clean_namespaces,
    finalize,
    normalize_arrays,
    transform,
    transform_with_steps,
    unwrap_soap,
)


# ── A) SOAP envelope unwrapping ────────────────────────────────────────────────

SOAP_11 = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <AddResponse xmlns="http://tempuri.org/">
      <AddResult>42</AddResult>
    </AddResponse>
  </soap:Body>
</soap:Envelope>"""

SOAP_12 = """<?xml version="1.0"?>
<env:Envelope xmlns:env="http://www.w3.org/2003/05/soap-envelope">
  <env:Body>
    <m:GetPriceResponse xmlns:m="http://example.org/prices">
      <m:Price>9.99</m:Price>
    </m:GetPriceResponse>
  </env:Body>
</env:Envelope>"""


def test_unwrap_soap_11():
    result = transform(SOAP_11)
    assert "AddResult" in result
    assert result["AddResult"] == 42


def test_unwrap_soap_12():
    result = transform(SOAP_12)
    assert "Price" in result
    assert result["Price"] == pytest.approx(9.99)


# ── B) Namespace cleaning ──────────────────────────────────────────────────────

def test_namespace_prefix_stripped():
    xml = "<ns2:Root><ns2:Name>Alice</ns2:Name></ns2:Root>"
    result = transform(xml)
    # root element becomes top-level key; namespace prefix stripped from both
    assert "Root" in result
    assert result["Root"]["Name"] == "Alice"
    assert "ns2:Name" not in result.get("Root", {})


def test_xmlns_attrs_removed():
    xml = '<Root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><Value>1</Value></Root>'
    result = transform(xml)
    root = result["Root"]
    assert "@xmlns:xsi" not in root
    assert root["Value"] == 1


# ── C) Array normalisation ────────────────────────────────────────────────────

def test_array_normalisation_single_element():
    xml = "<Items><Item><id>1</id></Item></Items>"
    result = transform(xml, transform_config={"arrays": ["Item"]})
    items = result["Items"]
    assert isinstance(items["Item"], list)
    assert len(items["Item"]) == 1


def test_array_normalisation_already_list():
    xml = "<Items><Item><id>1</id></Item><Item><id>2</id></Item></Items>"
    result = transform(xml, transform_config={"arrays": ["Item"]})
    items = result["Items"]
    assert isinstance(items["Item"], list)
    assert len(items["Item"]) == 2


# ── D) Mapping operations ──────────────────────────────────────────────────────

def test_mapping_select():
    data = {"a": 1, "b": 2, "c": 3}
    result = apply_mapping(data, {"select": ["a", "c"]})
    assert result == {"a": 1, "c": 3}
    assert "b" not in result


def test_mapping_exclude():
    data = {"a": 1, "b": 2, "c": 3}
    result = apply_mapping(data, {"exclude": ["b"]})
    assert "b" not in result
    assert result["a"] == 1 and result["c"] == 3


def test_mapping_rename():
    data = {"old_name": "value"}
    result = apply_mapping(data, {"rename": {"old_name": "new_name"}})
    assert "new_name" in result
    assert "old_name" not in result


def test_mapping_flatten():
    data = {"outer": {"inner_a": 1, "inner_b": 2}, "top": "x"}
    result = apply_mapping(data, {"flatten": True})
    assert result == {"inner_a": 1, "inner_b": 2, "top": "x"}


# ── E) Type conversion ─────────────────────────────────────────────────────────

def test_finalize_bool_true():
    assert finalize("true") is True
    assert finalize("True") is True


def test_finalize_bool_false():
    assert finalize("false") is False


def test_finalize_integer():
    assert finalize("42") == 42
    assert isinstance(finalize("42"), int)


def test_finalize_float():
    assert finalize("3.14") == pytest.approx(3.14)


def test_finalize_removes_none():
    data = {"a": None, "b": "keep"}
    result = finalize(data)
    assert "a" not in result
    assert result["b"] == "keep"


# ── F) Invalid XML ─────────────────────────────────────────────────────────────

def test_invalid_xml_raises():
    with pytest.raises(XMLParseError):
        transform("not < valid xml >>>")


# ── G) Empty / no config ───────────────────────────────────────────────────────

def test_no_transform_config():
    xml = "<Root><Value>5</Value></Root>"
    result = transform(xml)
    assert result["Root"]["Value"] == 5


# ── H) Full calculator pipeline ───────────────────────────────────────────────

def test_full_calculator_pipeline():
    xml = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <MultiplyResponse xmlns="http://tempuri.org/">
      <MultiplyResult>56</MultiplyResult>
    </MultiplyResponse>
  </soap:Body>
</soap:Envelope>"""

    config = {
        "rename": {"MultiplyResult": "result"},
    }
    steps = transform_with_steps(xml, config)

    assert "after_unwrap" in steps
    assert "after_clean" in steps
    assert "after_normalize" in steps
    assert "after_mapping" in steps
    assert "final" in steps
    assert steps["final"]["result"] == 56


# ── I) transform_with_steps returns all intermediate states ───────────────────

def test_steps_all_keys_present():
    xml = "<Root><X>1</X></Root>"
    steps = transform_with_steps(xml)
    assert set(steps.keys()) == {"after_unwrap", "after_clean", "after_normalize", "after_mapping", "final"}


# ── Sprint 16 — Advanced config features ──────────────────────────────────────

def test_force_list_paths_single_element():
    xml = "<Items><Item>one</Item></Items>"
    result = transform(xml, {"force_list_paths": ["Item"]})
    items = result["Items"]["Item"]
    assert isinstance(items, list)
    assert items == ["one"]


def test_force_list_paths_multiple_elements_unchanged():
    xml = "<Items><Item>a</Item><Item>b</Item></Items>"
    result = transform(xml, {"force_list_paths": ["Item"]})
    items = result["Items"]["Item"]
    assert isinstance(items, list)
    assert len(items) == 2


def test_force_list_paths_not_applied_without_config():
    xml = "<Items><Item>one</Item></Items>"
    result = transform(xml)
    assert isinstance(result["Items"]["Item"], str)


def test_namespace_cleanup_removes_xmlns_attrs():
    xml = (
        '<Root xmlns:ns="http://example.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<ns:Value xsi:type="string">hello</ns:Value>'
        '</Root>'
    )
    result = transform(xml)
    # Top-level is Root; namespace attrs should be stripped from its children
    root = result.get("Root", result)
    for key in root:
        assert not key.startswith("@xmlns")
    assert "Value" in root


def test_namespace_cleanup_strips_prefix():
    xml = '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><Data>42</Data></soap:Body></soap:Envelope>'
    result = transform(xml)
    assert result == {"Data": 42}


# ── Sprint 16-bis — response_path, force_list alias, item_map ─────────────────

def test_response_path_extracts_nested_value():
    xml = "<Root><Inner><Value>42</Value></Inner></Root>"
    result = transform(xml, {"response_path": "Root.Inner"})
    assert result == {"Value": 42}


def test_response_path_no_match_returns_full_data():
    xml = "<Root><Value>1</Value></Root>"
    result = transform(xml, {"response_path": "Root.NonExistent.Deep"})
    assert "Root" in result


def test_force_list_alias_works_same_as_force_list_paths():
    xml = "<Items><Item>one</Item></Items>"
    result = transform(xml, {"force_list": ["Item"]})
    assert isinstance(result["Items"]["Item"], list)
    assert result["Items"]["Item"] == ["one"]


def test_item_map_applies_to_list_items():
    xml = "<Items><Item><OldName>Alice</OldName></Item><Item><OldName>Bob</OldName></Item></Items>"
    config = {
        "response_path": "Items.Item",
        "force_list_paths": ["Item"],
        "item_map": {"rename": {"OldName": "name"}},
    }
    result = transform(xml, config)
    assert isinstance(result, list)
    assert result[0]["name"] == "Alice"
    assert result[1]["name"] == "Bob"
