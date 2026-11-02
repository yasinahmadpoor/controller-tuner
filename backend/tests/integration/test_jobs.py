"""Integration tests for Phase 7 async optimization jobs."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import reset_settings_cache
from app.db.models.job import JobModel
from app.infrastructure.locks import system_ga_lock_key
from app.main import create_app
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
    monkeypatch.setenv("PERSIST_TRAJECTORIES", "false")
    reset_settings_cache()
    _upgrade_head(os.environ["DATABASE_URL"])
    _truncate_tables(os.environ["DATABASE_URL"])

    app = create_app()
    app.state.context.redis.sync().flushdb()
    with TestClient(app) as test_client:
        yield test_client

    reset_settings_cache()


def _create_ball_beam(client: TestClient) -> str:
    response = client.post(
        "/api/v1/systems",
        json={"source": {"type": "catalog", "catalog_id": "ball_beam"}},
    )
    assert response.status_code == 201, response.text
    return response.json()["system_id"]


def _payload(**overrides) -> dict:
    payload = {
        "ga_config": {
            "population_size": 5,
            "generations": 2,
            "seed": 42,
            "max_wall_clock": 30,
        },
        "async": True,
    }
    payload.update(overrides)
    return payload


def _use_fake_enqueuer(client: TestClient) -> list[str]:
    captured: list[str] = []
    client.app.state.context.job_service._enqueuer = captured.append
    return captured


def test_async_optimize_returns_202_and_worker_completes_job(client: TestClient):
    system_id = _create_ball_beam(client)
    captured = _use_fake_enqueuer(client)

    response = client.post(f"/api/v1/systems/{system_id}/optimize", json=_payload())

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["links"]["self"] == f"/api/v1/jobs/{body['job_id']}"
    assert body["links"]["events"].endswith("/events")
    assert captured == [body["job_id"]]

    run_optimization.apply(args=[body["job_id"]]).get()

    job = client.get(f"/api/v1/jobs/{body['job_id']}")
    assert job.status_code == 200, job.text
    job_body = job.json()
    assert job_body["status"] == "succeeded"
    assert job_body["result"]["run_id"] == body["run_id"]
    assert set(job_body["result"]["controller_parameters"]) == {"Kp", "Ki", "Kd"}

    detail = client.get(f"/api/v1/optimizations/{body['run_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "succeeded"


def test_second_optimization_while_locked_returns_409(client: TestClient):
    system_id = _create_ball_beam(client)
    _use_fake_enqueuer(client)
    redis = client.app.state.context.redis.sync()
    redis.set(system_ga_lock_key(system_id), "other-token")

    response = client.post(f"/api/v1/systems/{system_id}/optimize", json=_payload())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "optimization_in_progress"
    redis.delete(system_ga_lock_key(system_id))


def test_queue_depth_limit_returns_429(client: TestClient):
    system_id = _create_ball_beam(client)
    _use_fake_enqueuer(client)
    redis = client.app.state.context.redis.sync()
    redis.delete("ga")
    redis.lpush("ga", *(["queued"] * client.app.state.context.settings.ga_queue_max_depth))

    response = client.post(f"/api/v1/systems/{system_id}/optimize", json=_payload())

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "job_queue_full"
    redis.delete("ga")


def test_enqueue_failure_marks_job_and_run_failed(client: TestClient):
    system_id = _create_ball_beam(client)

    def fail(_: str) -> None:
        raise RuntimeError("broker down")

    client.app.state.context.job_service._enqueuer = fail

    response = client.post(f"/api/v1/systems/{system_id}/optimize", json=_payload())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_not_ready"

    SessionLocal = sessionmaker(
        bind=client.app.state.context.engine, autoflush=False, expire_on_commit=False
    )
    with SessionLocal() as session:
        job = session.scalars(select(JobModel).order_by(JobModel.created_at.desc())).first()
        assert job is not None
        assert job.status == "failed"
        assert job.error is not None
        assert session.get(type(job), job.id) is not None


def test_cancel_queued_job_is_idempotent_and_releases_lock(client: TestClient):
    system_id = _create_ball_beam(client)
    _use_fake_enqueuer(client)
    created = client.post(f"/api/v1/systems/{system_id}/optimize", json=_payload())
    assert created.status_code == 202, created.text
    body = created.json()

    cancelled = client.post(f"/api/v1/jobs/{body['job_id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    again = client.post(f"/api/v1/jobs/{body['job_id']}/cancel")
    assert again.status_code == 200
    assert again.json()["status"] == "cancelled"

    redis = client.app.state.context.redis.sync()
    assert redis.exists(system_ga_lock_key(system_id)) == 0
    detail = client.get(f"/api/v1/optimizations/{body['run_id']}")
    assert detail.json()["status"] == "cancelled"


def test_job_not_found(client: TestClient):
    response = client.get("/api/v1/jobs/not-a-uuid")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"
