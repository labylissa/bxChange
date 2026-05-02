"""CRUD — mTLS Certificates."""
import hashlib
import uuid
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_developer_or_above
from app.models.mtls_certificate import MTLSCertificate
from app.models.user import User
from app.schemas.mtls_certificate import MTLSCertificateCreate, MTLSCertificateRead

router = APIRouter(prefix="/mtls/certificates", tags=["mtls"])

_401 = {"description": "Non authentifié"}
_403 = {"description": "Accès refusé"}
_404 = {"description": "Certificat introuvable"}


def _parse_cert(pem: str) -> tuple[str, str, str, datetime, datetime]:
    """Return (fingerprint_sha256, subject_dn, issuer_dn, valid_from, valid_until)."""
    try:
        cert = x509.load_pem_x509_certificate(pem.encode())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certificat PEM invalide : {exc}",
        )
    der = cert.public_bytes(Encoding.DER)
    fingerprint = hashlib.sha256(der).hexdigest()
    subject_dn = cert.subject.rfc4514_string()
    issuer_dn = cert.issuer.rfc4514_string()
    valid_from = cert.not_valid_before_utc.replace(tzinfo=None)
    valid_until = cert.not_valid_after_utc.replace(tzinfo=None)
    return fingerprint, subject_dn, issuer_dn, valid_from, valid_until


async def _get_cert(cert_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession) -> MTLSCertificate:
    cert = (await db.execute(
        select(MTLSCertificate).where(
            MTLSCertificate.id == cert_id,
            MTLSCertificate.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return cert


@router.get(
    "",
    response_model=list[MTLSCertificateRead],
    summary="Lister les certificats mTLS",
    responses={200: {"description": "Liste des certificats"}, 401: _401},
)
async def list_certs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MTLSCertificateRead]:
    result = await db.execute(
        select(MTLSCertificate).where(MTLSCertificate.tenant_id == current_user.tenant_id)
    )
    return [MTLSCertificateRead.model_validate(c) for c in result.scalars().all()]


@router.post(
    "",
    response_model=MTLSCertificateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer un certificat mTLS",
    description=(
        "Enregistre un certificat client PEM. Le fingerprint SHA-256, le subject DN "
        "et les dates de validité sont extraits automatiquement."
    ),
    responses={
        201: {"description": "Certificat enregistré"},
        400: {"description": "Certificat PEM invalide ou expiré"},
        401: _401,
        403: _403,
        409: {"description": "Certificat déjà enregistré (fingerprint identique)"},
    },
)
async def create_cert(
    payload: MTLSCertificateCreate,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> MTLSCertificateRead:
    fingerprint, subject_dn, issuer_dn, valid_from, valid_until = _parse_cert(payload.certificate_pem)

    if valid_until < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce certificat est expiré",
        )

    existing = (await db.execute(
        select(MTLSCertificate).where(MTLSCertificate.fingerprint_sha256 == fingerprint)
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un certificat avec ce fingerprint est déjà enregistré",
        )

    cert = MTLSCertificate(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        certificate_pem=payload.certificate_pem,
        fingerprint_sha256=fingerprint,
        subject_dn=subject_dn,
        issuer_dn=issuer_dn,
        valid_from=valid_from,
        valid_until=valid_until,
        created_by=current_user.id,
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return MTLSCertificateRead.model_validate(cert)


@router.delete(
    "/{cert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Révoquer un certificat mTLS",
    responses={204: {"description": "Révoqué"}, 401: _401, 403: _403, 404: _404},
)
async def delete_cert(
    cert_id: uuid.UUID,
    current_user: User = Depends(require_developer_or_above),
    db: AsyncSession = Depends(get_db),
) -> None:
    cert = await _get_cert(cert_id, current_user.tenant_id, db)
    await db.delete(cert)
    await db.commit()
