"""Tests for WSDL file upload — POST /api/v1/connectors/upload-wsdl."""
import pathlib
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

FIXTURE_WSDL = pathlib.Path(__file__).parent / "fixtures" / "calculator_test.wsdl"

_NOT_WSDL_XML = b"<?xml version='1.0'?><root><item>data</item></root>"
_INVALID_XML = b"this is not xml at all <<<"


def _user(suffix: str | None = None) -> dict:
    tag = suffix or uuid.uuid4().hex[:8]
    return {
        "email": f"wsdl_user_{tag}@example.com",
        "password": "SecurePass123!",
        "full_name": "WSDL Test User",
    }


async def _auth_headers(client: AsyncClient, suffix: str | None = None) -> dict:
    u = _user(suffix)
    r = await client.post("/api/v1/auth/register", json=u)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Upload endpoint tests ───────────────────────────────────────────────────


async def test_upload_valid_wsdl(client: AsyncClient, tmp_path: pathlib.Path, monkeypatch):
    """Valid .wsdl file → 200 + operations list."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    headers = await _auth_headers(client, "valid")
    wsdl_bytes = FIXTURE_WSDL.read_bytes()

    r = await client.post(
        "/api/v1/connectors/upload-wsdl",
        headers=headers,
        files={"file": ("calculator.wsdl", wsdl_bytes, "application/xml")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "wsdl_file_id" in data
    assert "wsdl_file_path" in data
    assert data["filename"] == "calculator.wsdl"
    assert "Add" in data["operations"]
    assert "Subtract" in data["operations"]
    # File must exist on disk
    saved = (tmp_path / "wsdl" / f"{data['wsdl_file_id']}.wsdl")
    assert saved.exists()


async def test_upload_file_too_large(client: AsyncClient, tmp_path: pathlib.Path, monkeypatch):
    """File > 5 MB → 413."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    headers = await _auth_headers(client, "large")
    big_content = b"A" * (5 * 1024 * 1024 + 1)

    r = await client.post(
        "/api/v1/connectors/upload-wsdl",
        headers=headers,
        files={"file": ("big.wsdl", big_content, "application/xml")},
    )
    assert r.status_code == 413


async def test_upload_non_wsdl_extension(client: AsyncClient, tmp_path: pathlib.Path, monkeypatch):
    """File with unsupported extension (.pdf) → 400."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    headers = await _auth_headers(client, "ext")
    r = await client.post(
        "/api/v1/connectors/upload-wsdl",
        headers=headers,
        files={"file": ("document.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert r.status_code == 400
    assert "Extension" in r.json()["detail"]


async def test_upload_invalid_xml(client: AsyncClient, tmp_path: pathlib.Path, monkeypatch):
    """File with malformed XML → 400."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    headers = await _auth_headers(client, "badxml")
    r = await client.post(
        "/api/v1/connectors/upload-wsdl",
        headers=headers,
        files={"file": ("bad.wsdl", _INVALID_XML, "application/xml")},
    )
    assert r.status_code == 400
    assert "XML invalide" in r.json()["detail"]


async def test_upload_xml_without_wsdl_namespace(
    client: AsyncClient, tmp_path: pathlib.Path, monkeypatch
):
    """Valid XML but not a WSDL (wrong namespace) → 400."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    headers = await _auth_headers(client, "notwsdl")
    r = await client.post(
        "/api/v1/connectors/upload-wsdl",
        headers=headers,
        files={"file": ("config.xml", _NOT_WSDL_XML, "application/xml")},
    )
    assert r.status_code == 400
    assert "WSDL" in r.json()["detail"]


async def test_upload_unauthenticated(client: AsyncClient, tmp_path: pathlib.Path, monkeypatch):
    """Upload without token → 401/403."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    r = await client.post(
        "/api/v1/connectors/upload-wsdl",
        files={"file": ("x.wsdl", b"<x/>", "application/xml")},
    )
    assert r.status_code in (401, 403)


# ── Connector creation with wsdl_source=upload ─────────────────────────────


async def test_create_connector_with_wsdl_upload(
    client: AsyncClient, tmp_path: pathlib.Path, monkeypatch
):
    """Upload WSDL then create connector with wsdl_source=upload → 201."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    headers = await _auth_headers(client, "create_upload")
    wsdl_bytes = FIXTURE_WSDL.read_bytes()

    # Step 1: upload
    up = await client.post(
        "/api/v1/connectors/upload-wsdl",
        headers=headers,
        files={"file": ("calc.wsdl", wsdl_bytes, "application/xml")},
    )
    assert up.status_code == 200
    file_id = up.json()["wsdl_file_id"]

    # Step 2: create connector
    r = await client.post(
        "/api/v1/connectors",
        headers=headers,
        json={
            "name": "Calculator Upload",
            "type": "soap",
            "wsdl_source": "upload",
            "wsdl_file_id": file_id,
            "auth_type": "none",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["wsdl_source"] == "upload"
    assert data["wsdl_file_path"] is not None
    assert file_id in data["wsdl_file_path"]


async def test_create_connector_upload_file_missing(
    client: AsyncClient, tmp_path: pathlib.Path, monkeypatch
):
    """Try to create connector with a non-existent wsdl_file_id → 400."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")
    (tmp_path / "wsdl").mkdir(parents=True, exist_ok=True)

    headers = await _auth_headers(client, "missing_file")
    r = await client.post(
        "/api/v1/connectors",
        headers=headers,
        json={
            "name": "Ghost Connector",
            "type": "soap",
            "wsdl_source": "upload",
            "wsdl_file_id": "nonexistent-uuid-1234",
            "auth_type": "none",
        },
    )
    assert r.status_code == 400
    assert "introuvable" in r.json()["detail"]


# ── Delete connector removes local WSDL file ───────────────────────────────


async def test_delete_connector_removes_wsdl_file(
    client: AsyncClient, tmp_path: pathlib.Path, monkeypatch
):
    """Deleting a connector with wsdl_source=upload removes the local file."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    headers = await _auth_headers(client, "delete_file")
    wsdl_bytes = FIXTURE_WSDL.read_bytes()

    # Upload
    up = await client.post(
        "/api/v1/connectors/upload-wsdl",
        headers=headers,
        files={"file": ("calc.wsdl", wsdl_bytes, "application/xml")},
    )
    assert up.status_code == 200
    file_id = up.json()["wsdl_file_id"]
    saved_file = tmp_path / "wsdl" / f"{file_id}.wsdl"
    assert saved_file.exists()

    # Create connector
    cr = await client.post(
        "/api/v1/connectors",
        headers=headers,
        json={
            "name": "Temp Connector",
            "type": "soap",
            "wsdl_source": "upload",
            "wsdl_file_id": file_id,
            "auth_type": "none",
        },
    )
    assert cr.status_code == 201
    connector_id = cr.json()["id"]

    # Delete connector
    dr = await client.delete(f"/api/v1/connectors/{connector_id}", headers=headers)
    assert dr.status_code == 204

    # File must be gone
    assert not saved_file.exists()


# ── Execute connector with local WSDL (mocked SOAP call) ───────────────────


async def test_execute_connector_local_wsdl(
    client: AsyncClient, tmp_path: pathlib.Path, monkeypatch
):
    """Execute a connector backed by an uploaded WSDL (soap_engine mocked)."""
    import app.api.v1.connectors as mod
    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "wsdl")

    headers = await _auth_headers(client, "exec_local")
    wsdl_bytes = FIXTURE_WSDL.read_bytes()

    # Upload
    up = await client.post(
        "/api/v1/connectors/upload-wsdl",
        headers=headers,
        files={"file": ("calc.wsdl", wsdl_bytes, "application/xml")},
    )
    assert up.status_code == 200
    file_id = up.json()["wsdl_file_id"]

    # Create connector
    cr = await client.post(
        "/api/v1/connectors",
        headers=headers,
        json={
            "name": "Local Calc",
            "type": "soap",
            "wsdl_source": "upload",
            "wsdl_file_id": file_id,
            "auth_type": "none",
        },
    )
    assert cr.status_code == 201
    connector_id = cr.json()["id"]

    # Execute — mock the soap engine to avoid real network call
    mock_result = {"AddResult": 8}
    with patch(
        "app.services.soap_engine.execute",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        ex = await client.post(
            f"/api/v1/connectors/{connector_id}/execute",
            headers=headers,
            json={"params": {"operation": "Add", "intA": 5, "intB": 3}},
        )
    assert ex.status_code == 200
    assert ex.json()["status"] == "success"
