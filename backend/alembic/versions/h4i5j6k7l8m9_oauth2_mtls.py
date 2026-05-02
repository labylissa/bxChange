"""oauth2_clients + mtls_certificates

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-05-02

"""
from alembic import op


revision = "h4i5j6k7l8m9"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS oauth2_clients (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            client_id VARCHAR NOT NULL UNIQUE,
            client_secret_hash VARCHAR NOT NULL,
            client_secret_preview VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            scopes JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            token_ttl_seconds INTEGER NOT NULL DEFAULT 3600,
            allowed_ips JSONB NOT NULL DEFAULT '[]',
            last_used_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_by UUID NOT NULL REFERENCES users(id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_oauth2_clients_tenant_id ON oauth2_clients (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_oauth2_clients_client_id ON oauth2_clients (client_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS mtls_certificates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR NOT NULL,
            certificate_pem TEXT NOT NULL,
            fingerprint_sha256 VARCHAR NOT NULL UNIQUE,
            subject_dn VARCHAR NOT NULL,
            issuer_dn VARCHAR NOT NULL,
            valid_from TIMESTAMP NOT NULL,
            valid_until TIMESTAMP NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_used_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_by UUID NOT NULL REFERENCES users(id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_mtls_certificates_tenant_id ON mtls_certificates (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mtls_certificates_fingerprint ON mtls_certificates (fingerprint_sha256)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mtls_certificates_fingerprint")
    op.execute("DROP INDEX IF EXISTS ix_mtls_certificates_tenant_id")
    op.execute("DROP TABLE IF EXISTS mtls_certificates")
    op.execute("DROP INDEX IF EXISTS ix_oauth2_clients_client_id")
    op.execute("DROP INDEX IF EXISTS ix_oauth2_clients_tenant_id")
    op.execute("DROP TABLE IF EXISTS oauth2_clients")
