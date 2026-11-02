"""Celery maintenance tasks for retention and artifact cleanup."""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.unit_of_work import UnitOfWork
from app.infrastructure.progress import clear_job_keys
from app.workers.celery_app import celery_app
from app.workers.runtime import build_worker_runtime


@celery_app.task(name="app.workers.maintenance.cleanup_terminal_jobs")
def cleanup_terminal_jobs() -> int:
    runtime = build_worker_runtime()
    redis = runtime.redis.sync()
    try:
        now = datetime.now(UTC)
        with UnitOfWork(runtime.session_factory) as uow:
            assert uow.jobs is not None
            expired = uow.jobs.delete_expired(now)
            for job in expired:
                clear_job_keys(redis, str(job.id))
                uow.jobs.delete(job.id)
            uow.commit()
        return len(expired)
    finally:
        runtime.close()


@celery_app.task(name="app.workers.maintenance.cleanup_expired_runs")
def cleanup_expired_runs() -> int:
    runtime = build_worker_runtime()
    try:
        now = datetime.now(UTC)
        with UnitOfWork(runtime.session_factory) as uow:
            assert uow.optimization_runs is not None
            assert uow.simulation_runs is not None
            expired_optimizations = uow.optimization_runs.delete_expired(now)
            expired_simulations = uow.simulation_runs.delete_expired(now)
            for run in expired_optimizations:
                uow.optimization_runs.delete(run.id)
            for run in expired_simulations:
                uow.simulation_runs.delete(run.id)
            uow.commit()
        return len(expired_optimizations) + len(expired_simulations)
    finally:
        runtime.close()


@celery_app.task(name="app.workers.maintenance.cleanup_orphan_artifacts")
def cleanup_orphan_artifacts() -> int:
    runtime = build_worker_runtime()
    try:
        with UnitOfWork(runtime.session_factory) as uow:
            assert uow.artifacts is not None
            orphans = uow.artifacts.delete_unreferenced()
            keys = [artifact.storage_key for artifact in orphans]
            uow.commit()
        for key in keys:
            runtime.storage.delete(key)
        return len(keys)
    finally:
        runtime.close()


@celery_app.task(name="app.workers.maintenance.delete_expired_systems")
def delete_expired_systems() -> int:
    runtime = build_worker_runtime()
    try:
        return runtime.system_service.delete_expired(datetime.now(UTC))
    finally:
        runtime.close()
