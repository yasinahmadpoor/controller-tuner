"""Celery task that executes a persisted async GA optimization job."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.api.schemas import OptimizeRequest
from app.core.cancellation import JobCancelled
from app.core.logging import get_logger
from app.db.unit_of_work import UnitOfWork
from app.engines.auto_tune_adapter import AutoTuneEngineAdapter
from app.infrastructure.locks import release_system_lock
from app.infrastructure.progress import (
    is_cancel_requested,
    publish_progress,
    publish_terminal,
)
from app.services.simulation_service import _MaterializedCode
from app.workers.celery_app import celery_app
from app.workers.runtime import build_worker_runtime

logger = get_logger(__name__)


@celery_app.task(bind=True, acks_late=True, name="app.workers.ga_tasks.run_optimization")
def run_optimization(self, job_id: str) -> str:
    logger.info("ga_job_started", job_id=job_id)
    runtime = build_worker_runtime()
    redis = runtime.redis.sync()
    job_uuid = uuid.UUID(job_id)
    lock_token: str | None = None
    system_id: uuid.UUID | None = None
    request_payload: dict[str, Any] | None = None
    already_terminal = False

    try:
        with UnitOfWork(runtime.session_factory) as uow:
            assert uow.jobs is not None
            assert uow.optimization_runs is not None
            job = uow.jobs.get(job_uuid)
            if job is None:
                return "missing"
            lock_token = job.lock_token
            if job.status in {"succeeded", "failed", "cancelled"}:
                already_terminal = True
            else:
                run = uow.optimization_runs.get(job.run_id)
                if run is None:
                    uow.jobs.mark_failed(
                        job, error={"type": "RunNotFound", "message": "run row missing"}
                    )
                    uow.commit()
                    already_terminal = True
                else:
                    system_id = run.system_id
                    request_payload = dict(run.request or {})
                    uow.jobs.mark_running(job, worker_id=getattr(self.request, "hostname", None))
                    uow.commit()
        if already_terminal or system_id is None or request_payload is None:
            return "skipped"

        spec, code = runtime.system_service.get_spec_and_code(str(system_id))
        request = OptimizeRequest.model_validate(request_payload)
        started_at = datetime.now(UTC)
        started = time.perf_counter()

        def on_progress(event: dict[str, Any]) -> None:
            publish_progress(
                redis,
                job_id,
                event,
                ttl_seconds=runtime.settings.job_retention_seconds,
            )

        def cancel_check() -> bool:
            return is_cancel_requested(redis, job_id)

        try:
            with _MaterializedCode(code) as code_path:
                result = AutoTuneEngineAdapter().optimize(
                    spec,
                    request,
                    code_path=code_path,
                    progress_callback=on_progress,
                    cancel_check=cancel_check,
                )
        except JobCancelled:
            logger.info("ga_job_cancelled", job_id=job_id)
            _finish_cancelled(runtime, redis, job_uuid, job_id)
            return "cancelled"
        except Exception as exc:
            logger.exception("ga_job_failed", job_id=job_id, error=str(exc))
            _finish_failed(runtime, redis, job_uuid, job_id, exc)
            return "failed"

        duration_ms = int((time.perf_counter() - started) * 1000)
        finished_at = datetime.now(UTC)
        terminal_status = "succeeded"
        with UnitOfWork(runtime.session_factory) as uow:
            assert uow.jobs is not None
            assert uow.optimization_runs is not None
            job = uow.jobs.get(job_uuid)
            run = uow.optimization_runs.get(job.run_id) if job is not None else None
            if job is None or run is None or job.status in {"succeeded", "failed", "cancelled"}:
                return "stale"
            if cancel_check():
                uow.jobs.mark_cancelled(job)
                uow.optimization_runs.finish(run, status="cancelled", finished_at=finished_at)
                terminal_status = "cancelled"
            else:
                uow.optimization_runs.finish(
                    run,
                    status="succeeded",
                    result=result,
                    duration_ms=duration_ms,
                    started_at=started_at,
                    finished_at=finished_at,
                )
                uow.jobs.mark_succeeded(job, progress=result.get("progress", {}))
            uow.commit()
        publish_terminal(
            redis,
            job_id,
            terminal_status,
            ttl_seconds=runtime.settings.job_retention_seconds,
        )
        logger.info(
            "ga_job_finished",
            job_id=job_id,
            status=terminal_status,
            duration_ms=duration_ms,
        )
        return terminal_status
    finally:
        if lock_token is not None and system_id is not None:
            release_system_lock(redis, system_id, lock_token)
        runtime.close()


def _finish_cancelled(runtime: Any, redis: Any, job_uuid: uuid.UUID, job_id: str) -> None:
    with UnitOfWork(runtime.session_factory) as uow:
        assert uow.jobs is not None
        assert uow.optimization_runs is not None
        job = uow.jobs.get(job_uuid)
        if job is None:
            return
        run = uow.optimization_runs.get(job.run_id)
        uow.jobs.mark_cancelled(job)
        if run is not None:
            uow.optimization_runs.finish(run, status="cancelled", finished_at=datetime.now(UTC))
        uow.commit()
    publish_terminal(
        redis,
        job_id,
        "cancelled",
        ttl_seconds=runtime.settings.job_retention_seconds,
    )


def _finish_failed(
    runtime: Any, redis: Any, job_uuid: uuid.UUID, job_id: str, exc: Exception
) -> None:
    error = {"type": type(exc).__name__, "message": str(exc)}
    with UnitOfWork(runtime.session_factory) as uow:
        assert uow.jobs is not None
        assert uow.optimization_runs is not None
        job = uow.jobs.get(job_uuid)
        if job is None:
            return
        run = uow.optimization_runs.get(job.run_id)
        uow.jobs.mark_failed(job, error=error)
        if run is not None:
            uow.optimization_runs.finish(
                run,
                status="failed",
                error=error,
                finished_at=datetime.now(UTC),
            )
        uow.commit()
    publish_terminal(
        redis,
        job_id,
        "failed",
        ttl_seconds=runtime.settings.job_retention_seconds,
        extra={"error": error},
    )
