from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SystemModel(Base):
    """Canonical system registry row (immutable metadata after creation)."""

    __tablename__ = "systems"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(nullable=True)
    objective: Mapped[str | None] = mapped_column(nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_ref: Mapped[str | None] = mapped_column(nullable=True)
    num_states: Mapped[int]
    num_inputs: Mapped[int]
    capabilities: Mapped[list[str]] = mapped_column(JSONB)
    simulation_defaults: Mapped[dict[str, Any]] = mapped_column(JSONB)
    optimization_defaults: Mapped[dict[str, Any]] = mapped_column(JSONB)
    artifact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
    )
    code_sha256: Mapped[str] = mapped_column(String(64))
    code_size: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)

    artifact = relationship("ArtifactModel", lazy="joined")

    __table_args__ = (Index("ix_systems_created_at", "created_at"),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "objective": self.objective,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "num_states": self.num_states,
            "num_inputs": self.num_inputs,
            "capabilities": self.capabilities,
            "simulation_defaults": self.simulation_defaults,
            "optimization_defaults": self.optimization_defaults,
            "code_sha256": self.code_sha256,
            "code_size": self.code_size,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
        }
