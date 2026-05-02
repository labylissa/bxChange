"""add operation to connectors

Revision ID: b2c3d4e5f6a7
Revises: 8f9a0b1c2d3e
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = '8f9a0b1c2d3e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('connectors', sa.Column('operation', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('connectors', 'operation')
