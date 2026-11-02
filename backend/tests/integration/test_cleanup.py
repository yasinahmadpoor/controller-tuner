"""Retention and orphan-cleanup task tests (Phase 7)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import reset_settings_cache
from app.db.unit_of_work import UnitOfWork
from app.infrastructure.progress import events_key, publish_progress
from app.main import create_app
from app.workers.maintenance import (
    cleanup_expired_runs,
    cleanup_orphan_artifacts,
    cleanup_terminal_jobs,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _upgrade_head(database_url: str) -> None:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_command.upgrade(cfg, "head")


def _truncate_tables(database_url: str) -> None:
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE jobs, optimization_runs, simulation_runs, systems, "
                "artifacts RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()


@pytest.fixture
def client(ready_dependencies, test_env, monkeypatch, tmp_path):
    monkeypatch.setenv("ARTIFACT_DIR", str(tmp_path / "artifacts"))
    reset_settings_cache()
    _upgrade_head(os.environ["DATABASE_URL"])
    _truncate_tables(os.environ["DATABASE_URL"])
    app = create_app()
    app.state.context.redis.sync().flushdb()
    with TestClient(app) as test_client:
        yield test_client
    reset_settings_cache()


def _system_id(client: TestClient) -> UUID:
    response = client.post(
        "/api/v1/systems",
        json={"source": {"type": "catalog", "catalog_id": "ball_beam"}},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["system_id"])


def _expired_run(client: TestClient, system_id: UUID, run_status: str = "succeeded"):
    past = datetime.now(UTC) - timedelta(hours=1)
    with UnitOfWork(client.app.state.context.session_factory) as uow:
        assert uow.optimization_runs is not None
        run = uow.optimization_runs.create(
            system_id=system_id,
            status=run_status,
            expires_at=past,
        )
        uow.commit()
        return run.id


def test_cleanup_terminal_jobs_removes_expired_job_and_stream(client: TestClient):
    system_id = _system_id(client)
    run_id = _expired_run(client, system_id, "succeeded")
    past = datetime.now(UTC) - timedelta(hours=1)
    with UnitOfWork(client.app.state.context.session_factory) as uow:
        assert uow.jobs is not None
        job = uow.jobs.create(run_id=run_id, expires_at=past)
        job.status = "succeeded"
        uow.commit()
        job_id = job.id
    redis = client.app.state.context.redis.sync()
    publish_progress(redis, str(job_id), {"generation": 1})

    cleanup_terminal_jobs.apply().get()

    with UnitOfWork(client.app.state.context.session_factory) as uow:
        assert uow.jobs is not None
        assert uow.jobs.get(job_id) is None
    assert redis.exists(events_key(str(job_id))) == 0


def test_cleanup_expired_runs_removes_old_rows(client: TestClient):
    system_id = _system_id(client)
    run_id = _expired_run(client, system_id, "succeeded")

    cleanup_expired_runs.apply().get()

    with UnitOfWork(client.app.state.context.session_factory) as uow:
        assert uow.optimization_runs is not None
        assert uow.optimization_runs.get(run_id) is None


def test_cleanup_orphan_artifacts_removes_row_and_blob(client: TestClient):
    storage = client.app.state.context.storage
    key, _ = storage.write(b"orphan artifact")
    with UnitOfWork(client.app.state.context.session_factory) as uow:
        assert uow.artifacts is not None
        artifact = uow.artifacts.create(
            kind="trajectory",
            storage_backend="local",
            storage_key=key,
            sha256="0" * 64,
            size=15,
        )
        uow.commit()
        artifact_id = artifact.id

    cleanup_orphan_artifacts.apply().get()

    with UnitOfWork(client.app.state.context.session_factory) as uow:
        assert uow.artifacts is not None
        assert uow.artifacts.get(artifact_id) is None
    assert storage.exists(key) is False
