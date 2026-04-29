"""sprint12_super_admin_users_limit

Revision ID: a1b2c3d4e5f6
Revises: 053cebc17532
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "053cebc17532"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add users_limit column to subscriptions
    op.add_column("subscriptions", sa.Column("users_limit", sa.Integer(), nullable=True))

    # Extend user_role enum to include super_admin (PostgreSQL only)
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'super_admin' BEFORE 'admin'")
        )


def downgrade() -> None:
    op.drop_column("subscriptions", "users_limit")
    # Note: removing an enum value from PostgreSQL is not supported without recreating the type.
    # Downgrade leaves the super_admin value in the enum.
