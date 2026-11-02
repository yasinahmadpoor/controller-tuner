"""optimization_runs table

Revision ID: 0004_optimization_runs
Revises: 0003_simulation_runs
Create Date: 2026-11-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_optimization_runs"
down_revision: str | None = "0003_simulation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "optimization_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "system_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("systems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("best_params", postgresql.JSONB(), nullable=False),
        sa.Column("achieved_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("progress", postgresql.JSONB(), nullable=False),
        sa.Column("stop_reason", sa.String(32), nullable=True),
        sa.Column("num_evaluations", sa.Integer(), nullable=True),
        sa.Column("target_hit", postgresql.JSONB(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.Column("non_finite_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("ga_cost", sa.Float(), nullable=True),
        sa.Column("baseline_cost", sa.Float(), nullable=True),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_optimization_runs_system_id", "optimization_runs", ["system_id"])
    op.create_index("ix_optimization_runs_status", "optimization_runs", ["status"])
    op.create_index("ix_optimization_runs_expires_at", "optimization_runs", ["expires_at"])
    op.create_index(
        "ix_optimization_runs_system_created",
        "optimization_runs",
        ["system_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_optimization_runs_system_created", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_expires_at", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_status", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_system_id", table_name="optimization_runs")
    op.drop_table("optimization_runs")
