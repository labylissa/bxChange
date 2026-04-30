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
    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        connection.execute(sa.text(
            "CREATE TYPE idp_type AS ENUM ('saml', 'oidc')"
        ))
        idp_col = sa.Column(
            "idp_type",
            sa.Enum("saml", "oidc", name="idp_type", create_type=False),
            nullable=False,
        )
    else:
        idp_col = sa.Column("idp_type", sa.String(8), nullable=False)

    op.create_table(
        "sso_configs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        idp_col,
        sa.Column("entity_id", sa.String(512), nullable=False),
        sa.Column("sso_url", sa.String(512), nullable=False),
        sa.Column("certificate", sa.Text(), nullable=True),
        sa.Column("attr_mapping", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_sso_configs_tenant_id", "sso_configs", ["tenant_id"])

    op.create_table(
        "scim_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_scim_tokens_tenant_id", "scim_tokens", ["tenant_id"])

    op.create_table(
        "sso_domain_hints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "sso_config_id",
            sa.Uuid(),
            sa.ForeignKey("sso_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_sso_domain_hints_domain", "sso_domain_hints", ["domain"])


def downgrade() -> None:
    op.drop_table("sso_domain_hints")
    op.drop_table("scim_tokens")
    op.drop_table("sso_configs")

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("DROP TYPE IF EXISTS idp_type"))
