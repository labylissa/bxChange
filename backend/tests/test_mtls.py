"""Tests: mTLS certificate registration + fingerprint auth."""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from httpx import AsyncClient


def _make_cert_pem(days_valid: int = 365, cn: str = "TestClient") -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TestOrg"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "FR"),
    ])
    now = datetime.now(timezone.utc)
    if days_valid < 0:
        not_before = now + timedelta(days=days_valid - 1)
        not_after = now + timedelta(days=days_valid)
    else:
        not_before = now
        not_after = now + timedelta(days=days_valid)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(Encoding.PEM).decode()


def _fingerprint(pem: str) -> str:
    from cryptography.hazmat.primitives.serialization import Encoding as Enc
    cert = x509.load_pem_x509_certificate(pem.encode())
    return hashlib.sha256(cert.public_bytes(Enc.DER)).hexdigest()


async def _register_and_login(client: AsyncClient) -> str:
    tag = uuid.uuid4().hex[:8]
    r = await client.post("/api/v1/auth/register", json={
        "email": f"mtls_{tag}@example.com",
        "password": "Pass123!",
        "full_name": "mTLS User",
    })
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_register_cert(client: AsyncClient):
    token = await _register_and_login(client)
    pem = _make_cert_pem()

    r = await client.post(
        "/api/v1/mtls/certificates",
        json={"name": "BanqueXYZ Prod", "certificate_pem": pem},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["fingerprint_sha256"] == _fingerprint(pem)
    assert "TestClient" in data["subject_dn"]


@pytest.mark.asyncio
async def test_register_expired_cert(client: AsyncClient):
    token = await _register_and_login(client)
    pem = _make_cert_pem(days_valid=-1)  # already expired

    r = await client.post(
        "/api/v1/mtls/certificates",
        json={"name": "Expired", "certificate_pem": pem},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate_cert(client: AsyncClient):
    token = await _register_and_login(client)
    pem = _make_cert_pem(cn=f"Dup{uuid.uuid4().hex[:6]}")

    r1 = await client.post(
        "/api/v1/mtls/certificates",
        json={"name": "First", "certificate_pem": pem},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/mtls/certificates",
        json={"name": "Second", "certificate_pem": pem},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_mtls_fingerprint_accepted(client: AsyncClient):
    """Valid fingerprint header must be accepted on /execute."""
    token = await _register_and_login(client)
    pem = _make_cert_pem(cn=f"MTLSTest{uuid.uuid4().hex[:4]}")

    await client.post(
        "/api/v1/mtls/certificates",
        json={"name": "Test", "certificate_pem": pem},
        headers={"Authorization": f"Bearer {token}"},
    )
    fp = _fingerprint(pem)
    fake_id = str(uuid.uuid4())

    r = await client.post(
        f"/api/v1/connectors/{fake_id}/execute",
        json={"params": {}},
        headers={"X-Client-Cert-Fingerprint": fp},
    )
    # Auth accepted → 404 (connector not found), not 401
    assert r.status_code != 401, f"mTLS fingerprint rejected: {r.text}"


@pytest.mark.asyncio
async def test_unknown_fingerprint_rejected(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/connectors/{fake_id}/execute",
        json={"params": {}},
        headers={"X-Client-Cert-Fingerprint": "0" * 64},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_certs(client: AsyncClient):
    token = await _register_and_login(client)
    pem = _make_cert_pem(cn=f"List{uuid.uuid4().hex[:4]}")
    await client.post(
        "/api/v1/mtls/certificates",
        json={"name": "ToList", "certificate_pem": pem},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = await client.get("/api/v1/mtls/certificates", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_delete_cert(client: AsyncClient):
    token = await _register_and_login(client)
    pem = _make_cert_pem(cn=f"Del{uuid.uuid4().hex[:4]}")
    create_r = await client.post(
        "/api/v1/mtls/certificates",
        json={"name": "ToDelete", "certificate_pem": pem},
        headers={"Authorization": f"Bearer {token}"},
    )
    cert_id = create_r.json()["id"]

    del_r = await client.delete(
        f"/api/v1/mtls/certificates/{cert_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_r.status_code == 204
