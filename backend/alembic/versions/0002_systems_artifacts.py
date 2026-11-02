"""systems and artifacts tables

Revision ID: 0002_systems_artifacts
Revises: 0001_baseline
Create Date: 2026-11-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_systems_artifacts"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("storage_backend", sa.String(32), nullable=False),
        sa.Column("storage_key", sa.String(128), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_artifacts_sha256", "artifacts", ["sha256"])

    op.create_table(
        "systems",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("num_states", sa.Integer(), nullable=False),
        sa.Column("num_inputs", sa.Integer(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("simulation_defaults", postgresql.JSONB(), nullable=False),
        sa.Column("optimization_defaults", postgresql.JSONB(), nullable=False),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_sha256", sa.String(64), nullable=False),
        sa.Column("code_size", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_systems_source_type", "systems", ["source_type"])
    op.create_index("ix_systems_expires_at", "systems", ["expires_at"])
    op.create_index("ix_systems_created_at", "systems", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_systems_created_at", table_name="systems")
    op.drop_index("ix_systems_expires_at", table_name="systems")
    op.drop_index("ix_systems_source_type", table_name="systems")
    op.drop_table("systems")
    op.drop_index("ix_artifacts_sha256", table_name="artifacts")
    op.drop_table("artifacts")
