import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MTLSCertificateCreate(BaseModel):
    name: str
    certificate_pem: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "BanqueXYZ Prod",
                "certificate_pem": "-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----",
            }
        }
    }


class MTLSCertificateRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    fingerprint_sha256: str
    subject_dn: str
    issuer_dn: str
    valid_from: datetime
    valid_until: datetime
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    created_by: uuid.UUID

    model_config = {"from_attributes": True}
