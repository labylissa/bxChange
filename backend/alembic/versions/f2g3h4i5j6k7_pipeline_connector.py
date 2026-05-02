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
    # Use raw SQL for everything — avoids SQLAlchemy double-creating named Enum types
    op.execute("DO $$ BEGIN CREATE TYPE merge_strategy_enum AS ENUM ('merge','first','last','custom'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE execution_mode_enum AS ENUM ('sequential','parallel'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE on_error_enum AS ENUM ('stop','skip','continue'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            name VARCHAR NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            merge_strategy merge_strategy_enum NOT NULL DEFAULT 'merge',
            output_transform JSON,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pipelines_tenant_id ON pipelines (tenant_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_steps (
            id UUID PRIMARY KEY,
            pipeline_id UUID NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
            connector_id UUID NOT NULL REFERENCES connectors(id),
            step_order INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            execution_mode execution_mode_enum NOT NULL DEFAULT 'sequential',
            params_template JSON NOT NULL DEFAULT '{}',
            condition VARCHAR,
            on_error on_error_enum NOT NULL DEFAULT 'stop',
            timeout_seconds INTEGER NOT NULL DEFAULT 30
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pipeline_steps_pipeline_id ON pipeline_steps (pipeline_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_executions (
            id UUID PRIMARY KEY,
            pipeline_id UUID NOT NULL REFERENCES pipelines(id),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            triggered_by VARCHAR NOT NULL DEFAULT 'manual',
            status VARCHAR NOT NULL,
            input_params JSON NOT NULL DEFAULT '{}',
            result JSON NOT NULL DEFAULT '{}',
            steps_detail JSON NOT NULL DEFAULT '{}',
            duration_ms INTEGER NOT NULL DEFAULT 0,
            error_step INTEGER,
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pipeline_executions_pipeline_id ON pipeline_executions (pipeline_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pipeline_executions_tenant_id ON pipeline_executions (tenant_id)")


def downgrade() -> None:
    op.drop_table("pipeline_executions")
    op.drop_table("pipeline_steps")
    op.drop_table("pipelines")
    sa.Enum(name="on_error_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="execution_mode_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="merge_strategy_enum").drop(op.get_bind(), checkfirst=True)
