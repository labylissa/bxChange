"""pipeline_scheduler_webhook — nullable connector_id + pipeline_id on scheduled_jobs and webhook_endpoints

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'g3h4i5j6k7l8'
down_revision = 'f2g3h4i5j6k7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make connector_id nullable on scheduled_jobs, add pipeline_id
    op.alter_column("scheduled_jobs", "connector_id", nullable=True)
    op.add_column("scheduled_jobs", sa.Column(
        "pipeline_id", sa.Uuid(as_uuid=True),
        sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=True,
    ))

    # Make connector_id nullable on webhook_endpoints, add pipeline_id
    op.alter_column("webhook_endpoints", "connector_id", nullable=True)
    op.add_column("webhook_endpoints", sa.Column(
        "pipeline_id", sa.Uuid(as_uuid=True),
        sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("webhook_endpoints", "pipeline_id")
    op.alter_column("webhook_endpoints", "connector_id", nullable=False)
    op.drop_column("scheduled_jobs", "pipeline_id")
    op.alter_column("scheduled_jobs", "connector_id", nullable=False)
