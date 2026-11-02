from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models.artifact import ArtifactModel
from app.db.models.job import JobModel
from app.db.models.optimization_run import OptimizationRunModel
from app.db.models.simulation_run import SimulationRunModel
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
        """Delete artifact rows with no referencing system or run; return rows."""
        referenced = select(SystemModel.artifact_id).union(
            select(SimulationRunModel.trajectory_artifact_id).where(
                SimulationRunModel.trajectory_artifact_id.is_not(None)
            )
        )
        orphans = list(
            self.session.scalars(select(ArtifactModel).where(ArtifactModel.id.not_in(referenced)))
        )
        for artifact in orphans:
            self.session.delete(artifact)
        return orphans


class SimulationRunRepository(BaseRepository):
    """Persistence for manual simulation history (Phase 3)."""

    def create(
        self,
        *,
        system_id: UUID,
        controller_type: str,
        params: dict[str, Any],
        request: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
        initial_state: list[float] | None = None,
        seed: int | None = None,
        engine: str = "manual_tuner",
        status: str = "succeeded",
        metrics: dict[str, Any] | None = None,
        non_finite_metrics: list[str] | None = None,
        warnings: list[str] | None = None,
        error: dict[str, Any] | None = None,
        trajectory_artifact_id: UUID | None = None,
        duration_ms: int | None = None,
        expires_at: datetime | None = None,
    ) -> SimulationRunModel:
        run = SimulationRunModel(
            id=uuid4(),
            system_id=system_id,
            controller_type=controller_type,
            request=request or {},
            params=params,
            overrides=overrides or {},
            initial_state=initial_state,
            seed=seed,
            engine=engine,
            status=status,
            metrics=metrics or {},
            non_finite_metrics=non_finite_metrics or [],
            warnings=warnings or [],
            error=error,
            trajectory_artifact_id=trajectory_artifact_id,
            duration_ms=duration_ms,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self.session.add(run)
        return run

    def get(self, run_id: UUID) -> SimulationRunModel | None:
        return self.session.get(SimulationRunModel, run_id)

    def list(
        self,
        *,
        system_id: UUID | None = None,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[SimulationRunModel], int]:
        stmt = select(SimulationRunModel)
        if system_id is not None:
            stmt = stmt.where(SimulationRunModel.system_id == system_id)
        if status is not None:
            stmt = stmt.where(SimulationRunModel.status == status)
        stmt = stmt.order_by(SimulationRunModel.created_at.desc(), SimulationRunModel.id)
        total = self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        items = list(self.session.scalars(stmt.limit(limit).offset(offset)))
        return items, int(total or 0)

    def delete(self, run_id: UUID) -> bool:
        count = self.session.execute(
            delete(SimulationRunModel).where(SimulationRunModel.id == run_id)
        ).rowcount
        return bool(count)

    def delete_expired(self, now: datetime) -> list[SimulationRunModel]:
        stmt = select(SimulationRunModel).where(SimulationRunModel.expires_at < now)
        return list(self.session.scalars(stmt))


class OptimizationRunRepository(BaseRepository):
    """Persistence for GA optimization history (Phase 4)."""

    def create(
        self,
        *,
        system_id: UUID,
        request: dict[str, Any] | None = None,
        status: str = "succeeded",
        best_params: dict[str, Any] | None = None,
        achieved_metrics: dict[str, Any] | None = None,
        progress: dict[str, Any] | None = None,
        stop_reason: str | None = None,
        num_evaluations: int | None = None,
        target_hit: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        non_finite_metrics: list[str] | None = None,
        ga_cost: float | None = None,
        baseline_cost: float | None = None,
        error: dict[str, Any] | None = None,
        engine: str = "ga_tuner",
        duration_ms: int | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> OptimizationRunModel:
        run = OptimizationRunModel(
            id=uuid4(),
            system_id=system_id,
            engine=engine,
            status=status,
            request=request or {},
            best_params=best_params or {},
            achieved_metrics=achieved_metrics or {},
            progress=progress or {},
            stop_reason=stop_reason,
            num_evaluations=num_evaluations,
            target_hit=target_hit,
            warnings=warnings or [],
            non_finite_metrics=non_finite_metrics or [],
            ga_cost=ga_cost,
            baseline_cost=baseline_cost,
            error=error,
            duration_ms=duration_ms,
            created_at=datetime.now(UTC),
            started_at=started_at,
            finished_at=finished_at,
            expires_at=expires_at,
        )
        self.session.add(run)
        return run

    def get(self, run_id: UUID) -> OptimizationRunModel | None:
        return self.session.get(OptimizationRunModel, run_id)

    def list(
        self,
        *,
        system_id: UUID | None = None,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[OptimizationRunModel], int]:
        stmt = select(OptimizationRunModel)
        if system_id is not None:
            stmt = stmt.where(OptimizationRunModel.system_id == system_id)
        if status is not None:
            stmt = stmt.where(OptimizationRunModel.status == status)
        stmt = stmt.order_by(OptimizationRunModel.created_at.desc(), OptimizationRunModel.id)
        total = self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        items = list(self.session.scalars(stmt.limit(limit).offset(offset)))
        return items, int(total or 0)

    def delete(self, run_id: UUID) -> bool:
        count = self.session.execute(
            delete(OptimizationRunModel).where(OptimizationRunModel.id == run_id)
        ).rowcount
        return bool(count)

    def delete_expired(self, now: datetime) -> list[OptimizationRunModel]:
        stmt = select(OptimizationRunModel).where(OptimizationRunModel.expires_at < now)
        return list(self.session.scalars(stmt))

    def finish(
        self,
        run: OptimizationRunModel,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> OptimizationRunModel:
        payload = result or {}
        run.status = status
        run.best_params = payload.get("controller_parameters", {})
        run.achieved_metrics = payload.get("achieved_metrics", {})
        run.progress = payload.get("progress", {})
        run.stop_reason = payload.get("stop_reason")
        run.num_evaluations = payload.get("num_evaluations")
        run.target_hit = payload.get("target_hit")
        run.warnings = payload.get("warnings", [])
        run.non_finite_metrics = payload.get("non_finite_metrics", [])
        run.ga_cost = payload.get("ga_cost")
        run.baseline_cost = payload.get("baseline_cost")
        run.error = error
        run.duration_ms = duration_ms
        if started_at is not None:
            run.started_at = started_at
        run.finished_at = finished_at or datetime.now(UTC)
        return run


_TERMINAL_JOB_STATUSES = {"succeeded", "failed", "cancelled"}
_ALLOWED_JOB_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "failed", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
}


class JobRepository(BaseRepository):
    """Persistence and state transitions for async jobs (Phase 7)."""

    def create(
        self,
        *,
        run_id: UUID,
        run_type: str = "optimization",
        status: str = "queued",
        progress: dict[str, Any] | None = None,
        lock_token: str | None = None,
        expires_at: datetime | None = None,
    ) -> JobModel:
        job = JobModel(
            id=uuid4(),
            run_id=run_id,
            run_type=run_type,
            status=status,
            progress=progress or {},
            cancel_requested=False,
            lock_token=lock_token,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self.session.add(job)
        return job

    def get(self, job_id: UUID) -> JobModel | None:
        return self.session.get(JobModel, job_id)

    def list_active(self) -> list[JobModel]:
        stmt = select(JobModel).where(JobModel.status.in_(("queued", "running")))
        return list(self.session.scalars(stmt))

    def transition(
        self,
        job: JobModel,
        status: str,
        *,
        worker_id: str | None = None,
        progress: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> bool:
        if job.status in _TERMINAL_JOB_STATUSES:
            return False
        if status not in _ALLOWED_JOB_TRANSITIONS.get(job.status, set()):
            return False
        now = datetime.now(UTC)
        job.status = status
        if worker_id is not None:
            job.worker_id = worker_id
        if progress is not None:
            job.progress = progress
        if error is not None:
            job.error = error
        if status == "running" and job.started_at is None:
            job.started_at = now
        if status in _TERMINAL_JOB_STATUSES:
            job.finished_at = now
        return True

    def mark_running(self, job: JobModel, *, worker_id: str | None = None) -> bool:
        if job.status == "running":
            if worker_id is not None:
                job.worker_id = worker_id
            return True
        return self.transition(job, "running", worker_id=worker_id)

    def mark_succeeded(self, job: JobModel, *, progress: dict[str, Any] | None = None) -> bool:
        return self.transition(job, "succeeded", progress=progress)

    def mark_failed(
        self,
        job: JobModel,
        *,
        error: dict[str, Any] | None = None,
        progress: dict[str, Any] | None = None,
    ) -> bool:
        return self.transition(job, "failed", error=error, progress=progress)

    def mark_cancelled(self, job: JobModel, *, progress: dict[str, Any] | None = None) -> bool:
        return self.transition(job, "cancelled", progress=progress)

    def request_cancel(self, job: JobModel) -> bool:
        if job.status in _TERMINAL_JOB_STATUSES:
            return False
        job.cancel_requested = True
        return True

    def delete(self, job_id: UUID) -> bool:
        count = self.session.execute(delete(JobModel).where(JobModel.id == job_id)).rowcount
        return bool(count)

    def delete_expired(self, now: datetime) -> list[JobModel]:
        stmt = select(JobModel).where(JobModel.expires_at < now)
        return list(self.session.scalars(stmt))
