from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models.artifact import ArtifactModel
from app.db.models.system import SystemModel


class BaseRepository:
    def __init__(self, session: Session):
        self.session = session


class SystemRepository(BaseRepository):
    """Persistence for canonical system metadata (Phase 2)."""

    def create(
        self,
        *,
        name: str,
        description: str | None,
        objective: str | None,
        source_type: str,
        source_ref: str | None,
        num_states: int,
        num_inputs: int,
        capabilities: list[str],
        simulation_defaults: dict[str, Any],
        optimization_defaults: dict[str, Any],
        artifact_id: UUID,
        code_sha256: str,
        code_size: int,
        expires_at: datetime | None = None,
    ) -> SystemModel:
        system = SystemModel(
            id=uuid4(),
            name=name,
            description=description,
            objective=objective,
            source_type=source_type,
            source_ref=source_ref,
            num_states=num_states,
            num_inputs=num_inputs,
            capabilities=capabilities,
            simulation_defaults=simulation_defaults,
            optimization_defaults=optimization_defaults,
            artifact_id=artifact_id,
            code_sha256=code_sha256,
            code_size=code_size,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self.session.add(system)
        return system

    def get(self, system_id: UUID) -> SystemModel | None:
        return self.session.get(SystemModel, system_id)

    def list(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        source_type: str | None = None,
    ) -> tuple[list[SystemModel], int]:
        stmt = select(SystemModel)
        if source_type is not None:
            stmt = stmt.where(SystemModel.source_type == source_type)
        stmt = stmt.order_by(SystemModel.created_at.desc(), SystemModel.id)
        total = self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        items = list(self.session.scalars(stmt.limit(limit).offset(offset)))
        return items, int(total or 0)

    def delete(self, system_id: UUID) -> bool:
        count = self.session.execute(
            delete(SystemModel).where(SystemModel.id == system_id)
        ).rowcount
        return bool(count)

    def delete_expired(self, now: datetime) -> list[SystemModel]:
        stmt = select(SystemModel).where(SystemModel.expires_at < now)
        return list(self.session.scalars(stmt))


class ArtifactRepository(BaseRepository):
    """Persistence for content-addressed artifact metadata (Phase 2)."""

    def create(
        self,
        *,
        kind: str,
        storage_backend: str,
        storage_key: str,
        sha256: str,
        size: int,
        content_type: str | None = None,
    ) -> ArtifactModel:
        artifact = ArtifactModel(
            id=uuid4(),
            kind=kind,
            storage_backend=storage_backend,
            storage_key=storage_key,
            sha256=sha256,
            size=size,
            content_type=content_type,
            created_at=datetime.now(UTC),
        )
        self.session.add(artifact)
        return artifact

    def get(self, artifact_id: UUID) -> ArtifactModel | None:
        return self.session.get(ArtifactModel, artifact_id)

    def by_sha256(self, sha256: str) -> ArtifactModel | None:
        return self.session.scalar(
            select(ArtifactModel)
            .where(ArtifactModel.sha256 == sha256)
            .where(ArtifactModel.kind == "code")
            .order_by(ArtifactModel.created_at)
            .limit(1)
        )

    def delete_unreferenced(self) -> list[ArtifactModel]:
        """Delete artifact rows with no referencing system; returns deleted rows."""
        orphans = list(
            self.session.scalars(
                select(ArtifactModel).where(
                    ArtifactModel.id.not_in(select(SystemModel.artifact_id))
                )
            )
        )
        for artifact in orphans:
            self.session.delete(artifact)
        return orphans
