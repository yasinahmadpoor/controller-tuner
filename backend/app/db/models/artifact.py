from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArtifactModel(Base):
    """Content-addressed code/large-output artifact (metadata only)."""

    __tablename__ = "artifacts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(32))  # "code" | "trajectory"
    storage_backend: Mapped[str] = mapped_column(String(32))  # "local" | "s3"
    storage_key: Mapped[str] = mapped_column(String(128), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int]
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "kind": self.kind,
            "storage_backend": self.storage_backend,
            "storage_key": self.storage_key,
            "sha256": self.sha256,
            "size": self.size,
            "content_type": self.content_type,
            "created_at": self.created_at,
        }
