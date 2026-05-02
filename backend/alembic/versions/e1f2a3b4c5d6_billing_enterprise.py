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
    # New Enum types for PostgreSQL
    license_status_enum = sa.Enum(
        "trial", "active", "expired", "suspended", name="license_status_enum"
    )
    license_record_status = sa.Enum(
        "trial", "active", "expired", "suspended", name="license_record_status"
    )
    license_status_enum.create(op.get_bind(), checkfirst=True)
    license_record_status.create(op.get_bind(), checkfirst=True)

    # Add billing/license columns to tenants
    op.add_column("tenants", sa.Column(
        "license_status", license_status_enum, nullable=False, server_default="trial"
    ))
    op.add_column("tenants", sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
    op.add_column("tenants", sa.Column(
        "executions_limit", sa.Integer(), nullable=False, server_default="1000"
    ))
    op.add_column("tenants", sa.Column(
        "connectors_limit", sa.Integer(), nullable=False, server_default="100"
    ))
    op.add_column("tenants", sa.Column("contract_start", sa.DateTime(), nullable=True))
    op.add_column("tenants", sa.Column("contract_end", sa.DateTime(), nullable=True))
    op.add_column("tenants", sa.Column(
        "annual_price_cents", sa.Integer(), nullable=False, server_default="0"
    ))
    op.add_column("tenants", sa.Column(
        "executions_used", sa.Integer(), nullable=False, server_default="0"
    ))
    op.add_column("tenants", sa.Column(
        "connectors_count", sa.Integer(), nullable=False, server_default="0"
    ))
    op.add_column("tenants", sa.Column("stripe_customer_id", sa.String(), nullable=True))

    # Create licenses table
    op.create_table(
        "licenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("license_key", sa.String(), nullable=False),
        sa.Column("status", license_record_status, nullable=False, server_default="trial"),
        sa.Column("executions_limit", sa.Integer(), nullable=False),
        sa.Column("connectors_limit", sa.Integer(), nullable=False),
        sa.Column("contract_start", sa.DateTime(), nullable=False),
        sa.Column("contract_end", sa.DateTime(), nullable=False),
        sa.Column("annual_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.Column("suspension_reason", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("license_key"),
    )
    op.create_index("ix_licenses_tenant_id", "licenses", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_licenses_tenant_id", table_name="licenses")
    op.drop_table("licenses")

    op.drop_column("tenants", "stripe_customer_id")
    op.drop_column("tenants", "connectors_count")
    op.drop_column("tenants", "executions_used")
    op.drop_column("tenants", "annual_price_cents")
    op.drop_column("tenants", "contract_end")
    op.drop_column("tenants", "contract_start")
    op.drop_column("tenants", "connectors_limit")
    op.drop_column("tenants", "executions_limit")
    op.drop_column("tenants", "trial_ends_at")
    op.drop_column("tenants", "license_status")

    sa.Enum(name="license_record_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="license_status_enum").drop(op.get_bind(), checkfirst=True)
