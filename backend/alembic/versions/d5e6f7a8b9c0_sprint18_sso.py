"""sprint18_sso — SSO configs, SCIM tokens, domain hints

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        bind.execute(sa.text(
            "DO $$ BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'idp_type') THEN "
            "    CREATE TYPE idp_type AS ENUM ('saml', 'oidc'); "
            "  END IF; "
            "END $$;"
        ))
        bind.execute(sa.text(
            "CREATE TABLE IF NOT EXISTS sso_configs ("
            "  id UUID PRIMARY KEY, "
            "  tenant_id UUID NOT NULL REFERENCES tenants(id), "
            "  idp_type idp_type NOT NULL, "
            "  entity_id VARCHAR(512) NOT NULL, "
            "  sso_url VARCHAR(512) NOT NULL, "
            "  certificate TEXT, "
            "  attr_mapping JSON, "
            "  is_active BOOLEAN NOT NULL DEFAULT true, "
            "  created_at TIMESTAMP NOT NULL DEFAULT now() "
            ")"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_sso_configs_tenant_id ON sso_configs(tenant_id)"
        ))
        bind.execute(sa.text(
            "CREATE TABLE IF NOT EXISTS scim_tokens ("
            "  id UUID PRIMARY KEY, "
            "  tenant_id UUID NOT NULL REFERENCES tenants(id), "
            "  token_hash VARCHAR(64) NOT NULL UNIQUE, "
            "  name VARCHAR(255) NOT NULL, "
            "  expires_at TIMESTAMP, "
            "  is_active BOOLEAN NOT NULL DEFAULT true, "
            "  created_at TIMESTAMP NOT NULL DEFAULT now() "
            ")"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_scim_tokens_tenant_id ON scim_tokens(tenant_id)"
        ))
        bind.execute(sa.text(
            "CREATE TABLE IF NOT EXISTS sso_domain_hints ("
            "  id UUID PRIMARY KEY, "
            "  tenant_id UUID NOT NULL REFERENCES tenants(id), "
            "  domain VARCHAR(255) NOT NULL UNIQUE, "
            "  sso_config_id UUID NOT NULL REFERENCES sso_configs(id) ON DELETE CASCADE "
            ")"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_sso_domain_hints_domain ON sso_domain_hints(domain)"
        ))
    else:
        op.create_table(
            "sso_configs",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("idp_type", sa.String(8), nullable=False),
            sa.Column("entity_id", sa.String(512), nullable=False),
            sa.Column("sso_url", sa.String(512), nullable=False),
            sa.Column("certificate", sa.Text(), nullable=True),
            sa.Column("attr_mapping", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_table(
            "scim_tokens",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_table(
            "sso_domain_hints",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("domain", sa.String(255), nullable=False, unique=True),
            sa.Column("sso_config_id", sa.Uuid(), sa.ForeignKey("sso_configs.id"), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("sso_domain_hints")
    op.drop_table("scim_tokens")
    op.drop_table("sso_configs")

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("DROP TYPE IF EXISTS idp_type"))
