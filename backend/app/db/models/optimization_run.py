from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OptimizationRunModel(Base):
    """Persisted GA optimization run (Phase 4)."""

    __tablename__ = "optimization_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    system_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("systems.id", ondelete="CASCADE"),
        index=True,
    )
    engine: Mapped[str] = mapped_column(String(32), default="ga_tuner")
    status: Mapped[str] = mapped_column(String(16), default="succeeded", index=True)
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    best_params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    achieved_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    stop_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    num_evaluations: Mapped[int | None] = mapped_column(nullable=True)
    target_hit: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    non_finite_metrics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    ga_cost: Mapped[float | None] = mapped_column(nullable=True)
    baseline_cost: Mapped[float | None] = mapped_column(nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)

    __table_args__ = (Index("ix_optimization_runs_system_created", "system_id", "created_at"),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.id),
            "system_id": str(self.system_id),
            "run_type": "optimization",
            "engine": self.engine,
            "status": self.status,
            "request": self.request,
            "controller_parameters": self.best_params,
            "best_params": self.best_params,
            "achieved_metrics": self.achieved_metrics,
            "progress": self.progress,
            "stop_reason": self.stop_reason,
            "num_evaluations": self.num_evaluations,
            "target_hit": self.target_hit,
            "warnings": self.warnings,
            "non_finite_metrics": self.non_finite_metrics,
            "ga_cost": self.ga_cost,
            "baseline_cost": self.baseline_cost,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "expires_at": self.expires_at,
        }


OptimizationRun = OptimizationRunModel
