"""pipeline_connector — Pipeline, PipelineStep, PipelineExecution tables

Revision ID: f2g3h4i5j6k7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'f2g3h4i5j6k7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    merge_strategy_enum = sa.Enum("merge", "first", "last", "custom", name="merge_strategy_enum")
    execution_mode_enum = sa.Enum("sequential", "parallel", name="execution_mode_enum")
    on_error_enum = sa.Enum("stop", "skip", "continue", name="on_error_enum")
    merge_strategy_enum.create(op.get_bind(), checkfirst=True)
    execution_mode_enum.create(op.get_bind(), checkfirst=True)
    on_error_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "pipelines",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("merge_strategy", merge_strategy_enum, nullable=False, server_default="merge"),
        sa.Column("output_transform", sa.JSON, nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pipelines_tenant_id", "pipelines", ["tenant_id"])

    op.create_table(
        "pipeline_steps",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connector_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("connectors.id"), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("execution_mode", execution_mode_enum, nullable=False, server_default="sequential"),
        sa.Column("params_template", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("condition", sa.String, nullable=True),
        sa.Column("on_error", on_error_enum, nullable=False, server_default="stop"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="30"),
    )
    op.create_index("ix_pipeline_steps_pipeline_id", "pipeline_steps", ["pipeline_id"])

    op.create_table(
        "pipeline_executions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("pipelines.id"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("triggered_by", sa.String, nullable=False, server_default="manual"),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("input_params", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("result", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("steps_detail", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_step", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pipeline_executions_pipeline_id", "pipeline_executions", ["pipeline_id"])
    op.create_index("ix_pipeline_executions_tenant_id", "pipeline_executions", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("pipeline_executions")
    op.drop_table("pipeline_steps")
    op.drop_table("pipelines")
    sa.Enum(name="on_error_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="execution_mode_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="merge_strategy_enum").drop(op.get_bind(), checkfirst=True)
