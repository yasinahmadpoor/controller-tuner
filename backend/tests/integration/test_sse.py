"""Integration tests for Phase 7 SSE progress streaming."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import reset_settings_cache
from app.infrastructure.progress import (
    events_key,
    publish_progress,
    publish_terminal,
)
from app.main import create_app

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


def test_sse_replays_events_and_terminates(client: TestClient):
    job = _enqueue(client)
    redis = client.app.state.context.redis.sync()
    publish_progress(redis, job["job_id"], {"generation": 1, "Kp": 10.0})
    publish_progress(redis, job["job_id"], {"generation": 2, "Kp": 11.0})
    publish_terminal(redis, job["job_id"], "succeeded")

    response = client.get(f"/api/v1/jobs/{job['job_id']}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: progress" in body
    assert '"generation":1' in body
    assert '"generation":2' in body
    assert "event: done" in body
    assert '"status":"succeeded"' in body


def test_sse_last_event_id_replay_skips_seen_events(client: TestClient):
    job = _enqueue(client)
    redis = client.app.state.context.redis.sync()
    first_id = publish_progress(redis, job["job_id"], {"generation": 1, "marker": "first"})
    publish_progress(redis, job["job_id"], {"generation": 2, "marker": "second"})
    publish_terminal(redis, job["job_id"], "succeeded")

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}/events",
        headers={"Last-Event-ID": first_id},
    )

    assert response.status_code == 200
    body = response.text
    assert '"marker":"first"' not in body
    assert '"marker":"second"' in body
    assert "event: done" in body


def test_sse_terminal_fallback_when_stream_missing(client: TestClient):
    job = _enqueue(client)
    cancelled = client.post(f"/api/v1/jobs/{job['job_id']}/cancel")
    assert cancelled.status_code == 200
    redis = client.app.state.context.redis.sync()
    redis.delete(events_key(job["job_id"]))

    response = client.get(f"/api/v1/jobs/{job['job_id']}/events")

    assert response.status_code == 200
    body = response.text
    assert "event: done" in body
    assert '"status":"cancelled"' in body
