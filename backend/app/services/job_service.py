"""Async GA job orchestration: enqueue, polling, cancellation, and SSE state."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import sessionmaker

from app.api.schemas import OptimizeRequest
from app.core.config import Settings
from app.core.errors import (
    CapabilityNotSupported,
    JobNotCancellable,
    JobNotFound,
    JobQueueFull,
    OptimizationInProgress,
    ServiceNotReady,
)
from app.db.models.job import JobModel
from app.db.models.optimization_run import OptimizationRunModel
from app.db.unit_of_work import UnitOfWork
from app.domain.models import Capability
from app.infrastructure.locks import acquire_system_lock, release_system_lock
from app.infrastructure.progress import (
    latest_event,
    publish_terminal,
    set_cancel_flag,
)
from app.services.optimization_service import OptimizationService
from app.services.system_service import SystemService


def _parse_job_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise JobNotFound(f"job {value!r} not found", context={"job_id": value}) from exc


def _run_result(run: OptimizationRunModel) -> dict[str, Any] | None:
    if run.status != "succeeded":
        return None
    return {
        "success": True,
        "run_id": str(run.id),
        "engine": run.engine,
        "controller_parameters": run.best_params or {},
        "achieved_metrics": run.achieved_metrics or {},
        "ga_cost": run.ga_cost,
        "baseline_cost": run.baseline_cost,
        "progress": run.progress or {},
        "stop_reason": run.stop_reason,
        "num_evaluations": run.num_evaluations or 0,
        "target_hit": run.target_hit or {"nfe": None, "time": None, "generation": None},
        "warnings": run.warnings or [],
        "non_finite_metrics": run.non_finite_metrics or [],
    }


class JobService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        system_service: SystemService,
        optimization_service: OptimizationService,
        redis: Any,
        settings: Settings,
        enqueuer: Callable[[str], None] | None = None,
    ):
        self._session_factory = session_factory
        self._system_service = system_service
        self._optimization_service = optimization_service
        self._redis = redis
        self._settings = settings
        self._enqueuer = enqueuer

    # ------------------------------------------------------------------ #
    # Enqueue
    # ------------------------------------------------------------------ #
    def enqueue_optimization(
        self, system_id: str, request: OptimizeRequest
    ) -> tuple[JobModel, OptimizationRunModel]:
        spec, _ = self._system_service.get_spec_and_code(system_id)
        if Capability.OPTIMIZE not in spec.capabilities:
            raise CapabilityNotSupported(
                "system does not support optimization",
                context={"system_id": system_id},
            )
        self._optimization_service.validate_request(spec, request)

        queue_depth = int(self._redis.llen("ga") or 0)
        if queue_depth >= self._settings.ga_queue_max_depth:
            raise JobQueueFull(
                "the GA queue is full",
                context={"depth": queue_depth, "limit": self._settings.ga_queue_max_depth},
            )

        lock_ttl = int(self._settings.ga_task_time_limit) + 60
        lock = acquire_system_lock(self._redis, spec.system_id, lock_ttl)
        if lock is None:
            raise OptimizationInProgress(
                "an optimization is already running for this system",
                context={"system_id": system_id},
            )

        now = datetime.now(UTC)
        try:
            with UnitOfWork(self._session_factory) as uow:
                assert uow.optimization_runs is not None
                assert uow.jobs is not None
                run = uow.optimization_runs.create(
                    system_id=spec.system_id,
                    engine="ga_tuner",
                    status="queued",
                    request=request.model_dump(mode="json", by_alias=True),
                    expires_at=now + timedelta(days=self._settings.run_retention_days),
                )
                assert uow.session is not None
                uow.session.flush()
                job = uow.jobs.create(
                    run_id=run.id,
                    run_type="optimization",
                    status="queued",
                    lock_token=lock.token,
                    expires_at=now + timedelta(seconds=self._settings.job_retention_seconds),
                )
                uow.commit()
        except Exception:
            release_system_lock(self._redis, spec.system_id, lock.token)
            raise

        try:
            self._enqueue(str(job.id))
        except Exception as exc:
            with UnitOfWork(self._session_factory) as uow:
                assert uow.jobs is not None
                assert uow.optimization_runs is not None
                failed_job = uow.jobs.get(job.id)
                failed_run = uow.optimization_runs.get(run.id)
                if failed_job is not None:
                    uow.jobs.mark_failed(
                        failed_job,
                        error={"type": type(exc).__name__, "message": str(exc)},
                    )
                if failed_run is not None:
                    uow.optimization_runs.finish(
                        failed_run,
                        status="failed",
                        error={"type": type(exc).__name__, "message": str(exc)},
                        finished_at=datetime.now(UTC),
                    )
                uow.commit()
            release_system_lock(self._redis, spec.system_id, lock.token)
            raise ServiceNotReady("could not enqueue the optimization job") from exc

        return job, run

    def _enqueue(self, job_id: str) -> None:
        if self._enqueuer is not None:
            self._enqueuer(job_id)
            return
        from app.workers.ga_tasks import run_optimization

        run_optimization.apply_async(args=[job_id], queue="ga")

    # ------------------------------------------------------------------ #
    # Polling
    # ------------------------------------------------------------------ #
    def get_job(self, job_id: str) -> dict[str, Any]:
        parsed = _parse_job_uuid(job_id)
        with UnitOfWork(self._session_factory) as uow:
            assert uow.jobs is not None
            assert uow.optimization_runs is not None
            job = uow.jobs.get(parsed)
            if job is None:
                raise JobNotFound(f"job {job_id!r} not found", context={"job_id": job_id})
            run = uow.optimization_runs.get(job.run_id)
            system_id = run.system_id if run is not None else None
            payload = job.to_dict(
                system_id=system_id,
                result=_run_result(run) if run is not None else None,
            )
            payload["progress"] = dict(job.progress or {})
            latest = latest_event(self._redis, str(job.id))
            if latest is not None and latest["event"] == "progress":
                payload["progress"] = latest["data"]
            return payload

    # ------------------------------------------------------------------ #
    # Cancellation
    # ------------------------------------------------------------------ #
    def cancel_job(self, job_id: str) -> dict[str, Any]:
        parsed = _parse_job_uuid(job_id)
        terminal_published = False
        release_token: str | None = None
        release_system_id: uuid.UUID | None = None
        with UnitOfWork(self._session_factory) as uow:
            assert uow.jobs is not None
            assert uow.optimization_runs is not None
            job = uow.jobs.get(parsed)
            if job is None:
                raise JobNotFound(f"job {job_id!r} not found", context={"job_id": job_id})
            if job.status in {"succeeded", "failed"}:
                raise JobNotCancellable("job is already finished", context={"status": job.status})
            if job.status != "cancelled":
                set_cancel_flag(
                    self._redis,
                    str(job.id),
                    ttl_seconds=self._settings.job_retention_seconds,
                )
                uow.jobs.request_cancel(job)
                if job.status == "queued":
                    uow.jobs.mark_cancelled(job)
                    run = uow.optimization_runs.get(job.run_id)
                    if run is not None:
                        release_system_id = run.system_id
                        uow.optimization_runs.finish(
                            run,
                            status="cancelled",
                            finished_at=datetime.now(UTC),
                        )
                    release_token = job.lock_token
                    terminal_published = True
                uow.commit()
        if release_token is not None and release_system_id is not None:
            release_system_lock(self._redis, release_system_id, release_token)
        if terminal_published:
            publish_terminal(
                self._redis,
                str(parsed),
                "cancelled",
                ttl_seconds=self._settings.job_retention_seconds,
            )
        return self.get_job(str(parsed))
