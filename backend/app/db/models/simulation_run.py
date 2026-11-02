from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulationRunModel(Base):
    """Persisted manual simulation run (Phase 3)."""

    __tablename__ = "simulation_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("systems.id", ondelete="CASCADE"),
        index=True,
    )
    controller_type: Mapped[str] = mapped_column(String(8))
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSONB)
    initial_state: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    seed: Mapped[int | None] = mapped_column(nullable=True)
    engine: Mapped[str] = mapped_column(String(32), default="manual_tuner")
    status: Mapped[str] = mapped_column(String(16), default="succeeded", index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    non_finite_metrics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    trajectory_artifact_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)

    __table_args__ = (Index("ix_simulation_runs_system_created", "system_id", "created_at"),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.id),
            "system_id": str(self.system_id),
            "controller_type": self.controller_type,
            "request": self.request,
            "params": self.params,
            "overrides": self.overrides,
            "initial_state": self.initial_state,
            "seed": self.seed,
            "engine": self.engine,
            "status": self.status,
            "metrics": self.metrics,
            "non_finite_metrics": self.non_finite_metrics,
            "warnings": self.warnings,
            "error": self.error,
            "trajectory_artifact_id": (
                str(self.trajectory_artifact_id) if self.trajectory_artifact_id else None
            ),
            "duration_ms": self.duration_ms,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


SimulationRun = SimulationRunModel
