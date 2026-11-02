from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobModel(Base):
    """Durable async job state (Phase 7)."""

    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("optimization_runs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    run_type: Mapped[str] = mapped_column(String(16), default="optimization")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lock_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)

    __table_args__ = (
        Index("ix_jobs_status_created", "status", "created_at"),
        Index("ix_jobs_expires_at", "expires_at"),
    )

    def to_dict(
        self, *, system_id: UUID | None = None, result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "job_id": str(self.id),
            "run_id": str(self.run_id),
            "system_id": str(system_id) if system_id is not None else None,
            "status": self.status,
            "progress": self.progress,
            "cancel_requested": self.cancel_requested,
            "result": result,
            "error": self.error,
            "worker_id": self.worker_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "expires_at": self.expires_at,
        }


Job = JobModel
