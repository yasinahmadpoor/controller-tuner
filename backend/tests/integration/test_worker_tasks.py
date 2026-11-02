"""Worker task success/failure/cancellation tests (Phase 7)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import reset_settings_cache
from app.infrastructure.locks import system_ga_lock_key
from app.infrastructure.progress import set_cancel_flag
from app.main import create_app
from app.workers import ga_tasks
from app.workers.ga_tasks import run_optimization

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


def _enqueue(client: TestClient) -> dict:
    system = client.post(
        "/api/v1/systems",
        json={"source": {"type": "catalog", "catalog_id": "ball_beam"}},
    )
    assert system.status_code == 201, system.text
    client.app.state.context.job_service._enqueuer = lambda _job_id: None
    response = client.post(
        f"/api/v1/systems/{system.json()['system_id']}/optimize",
        json={
            "async": True,
            "ga_config": {
                "population_size": 5,
                "generations": 2,
                "seed": 42,
                "max_wall_clock": 30,
            },
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_worker_cancellation_marks_job_cancelled(client: TestClient):
    job = _enqueue(client)
    redis = client.app.state.context.redis.sync()
    set_cancel_flag(redis, job["job_id"], ttl_seconds=60)

    run_optimization.apply(args=[job["job_id"]]).get()

    polled = client.get(f"/api/v1/jobs/{job['job_id']}")
    assert polled.json()["status"] == "cancelled"
    detail = client.get(f"/api/v1/optimizations/{job['run_id']}")
    assert detail.json()["status"] == "cancelled"
    assert redis.exists(system_ga_lock_key(detail.json()["system_id"])) == 0


def test_worker_failure_marks_job_failed(client: TestClient, monkeypatch):
    job = _enqueue(client)

    class BoomAdapter:
        def optimize(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(ga_tasks, "AutoTuneEngineAdapter", BoomAdapter)

    run_optimization.apply(args=[job["job_id"]]).get()

    polled = client.get(f"/api/v1/jobs/{job['job_id']}")
    body = polled.json()
    assert body["status"] == "failed"
    assert body["error"]["message"] == "boom"
    detail = client.get(f"/api/v1/optimizations/{job['run_id']}")
    assert detail.json()["status"] == "failed"
