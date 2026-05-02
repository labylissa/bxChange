"""billing_enterprise — license fields on tenants + licenses table

Revision ID: e1f2a3b4c5d6
Revises: b2c3d4e5f6a7
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DO $$ BEGIN CREATE TYPE license_status_enum AS ENUM ('trial','active','expired','suspended'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE license_record_status AS ENUM ('trial','active','expired','suspended'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS license_status license_status_enum NOT NULL DEFAULT 'trial'")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS executions_limit INTEGER NOT NULL DEFAULT 1000")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS connectors_limit INTEGER NOT NULL DEFAULT 100")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS contract_start TIMESTAMP")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS contract_end TIMESTAMP")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS annual_price_cents INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS executions_used INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS connectors_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR")

    op.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            license_key VARCHAR NOT NULL UNIQUE,
            status license_record_status NOT NULL DEFAULT 'trial',
            executions_limit INTEGER NOT NULL,
            connectors_limit INTEGER NOT NULL,
            contract_start TIMESTAMP NOT NULL,
            contract_end TIMESTAMP NOT NULL,
            annual_price_cents INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMP NOT NULL,
            activated_at TIMESTAMP,
            suspended_at TIMESTAMP,
            suspension_reason VARCHAR
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_licenses_tenant_id ON licenses (tenant_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_licenses_tenant_id")
    op.execute("DROP TABLE IF EXISTS licenses")

    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS stripe_customer_id")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS connectors_count")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS executions_used")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS annual_price_cents")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS contract_end")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS contract_start")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS connectors_limit")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS executions_limit")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS trial_ends_at")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS license_status")

    op.execute("DROP TYPE IF EXISTS license_record_status")
    op.execute("DROP TYPE IF EXISTS license_status_enum")
