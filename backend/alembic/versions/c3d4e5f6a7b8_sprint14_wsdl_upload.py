"""sprint14_wsdl_upload

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        connection.execute(sa.text(
            "CREATE TYPE wsdl_source_type AS ENUM ('url', 'upload')"
        ))
        op.add_column(
            "connectors",
            sa.Column(
                "wsdl_source",
                sa.Enum("url", "upload", name="wsdl_source_type", create_type=False),
                nullable=False,
                server_default="url",
            ),
        )
    else:
        op.add_column(
            "connectors",
            sa.Column("wsdl_source", sa.String(16), nullable=False, server_default="url"),
        )

    op.add_column("connectors", sa.Column("wsdl_file_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("connectors", "wsdl_file_path")
    op.drop_column("connectors", "wsdl_source")

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("DROP TYPE IF EXISTS wsdl_source_type"))
