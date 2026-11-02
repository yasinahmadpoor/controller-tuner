"""empty baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-02 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Baseline: Phase 1 ships no production tables; later migrations add
    systems, artifacts, simulation_runs, optimization_runs and jobs.
    """
    op.execute("SELECT 1")


def downgrade() -> None:
    """No-op for the empty baseline."""
    op.execute("SELECT 1")
