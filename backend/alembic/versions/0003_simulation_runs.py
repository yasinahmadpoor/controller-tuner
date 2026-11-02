"""simulation_runs table

Revision ID: 0003_simulation_runs
Revises: 0002_systems_artifacts
Create Date: 2026-11-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_simulation_runs"
down_revision: str | None = "0002_systems_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "system_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("systems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("controller_type", sa.String(8), nullable=False),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("overrides", postgresql.JSONB(), nullable=False),
        sa.Column("initial_state", postgresql.JSONB(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("engine", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("non_finite_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column(
            "trajectory_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_simulation_runs_system_id", "simulation_runs", ["system_id"])
    op.create_index("ix_simulation_runs_status", "simulation_runs", ["status"])
    op.create_index("ix_simulation_runs_expires_at", "simulation_runs", ["expires_at"])
    op.create_index(
        "ix_simulation_runs_system_created",
        "simulation_runs",
        ["system_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_system_created", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_expires_at", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_status", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_system_id", table_name="simulation_runs")
    op.drop_table("simulation_runs")
