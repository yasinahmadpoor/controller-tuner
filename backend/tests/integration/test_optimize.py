"""Integration tests for the Phase 4 synchronous GA optimization workflow."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import reset_settings_cache
from app.db.models.optimization_run import OptimizationRunModel
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
                "TRUNCATE TABLE optimization_runs, simulation_runs, systems, "
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


def _optimize_payload(**overrides) -> dict:
    payload = {
        "ga_config": {
            "population_size": 5,
            "generations": 2,
            "seed": 42,
            "max_wall_clock": 30,
        }
    }
    payload.update(overrides)
    return payload


def test_optimize_runs_ga_and_persists_full_result(client: TestClient):
    system_id = _create_ball_beam(client)

    response = client.post(f"/api/v1/systems/{system_id}/optimize", json=_optimize_payload())

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["engine"] == "ga_tuner"
    assert payload["run_id"]
    assert set(payload["controller_parameters"]) == {"Kp", "Ki", "Kd"}
    assert payload["stop_reason"] in {"normal", "score_100", "wall_clock"}
    assert payload["num_evaluations"] > 0
    assert len(payload["progress"]["iteration"]) == 2
    assert len(payload["progress"]["Kp"]) == 2
    assert payload["target_hit"] == {"nfe": None, "time": None, "generation": None}

    detail = client.get(f"/api/v1/optimizations/{payload['run_id']}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["run_id"] == payload["run_id"]
    assert body["system_id"] == system_id
    assert body["run_type"] == "optimization"
    assert body["best_params"] == payload["controller_parameters"]
    assert body["request"]["ga_config"]["population_size"] == 5
    assert body["ga_cost"] is not None

    engine = client.app.state.context.engine
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(OptimizationRunModel)) == 1


def test_optimize_is_seeded_and_lists_history(client: TestClient):
    system_id = _create_ball_beam(client)

    first = client.post(f"/api/v1/systems/{system_id}/optimize", json=_optimize_payload())
    second = client.post(f"/api/v1/systems/{system_id}/optimize", json=_optimize_payload())
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["controller_parameters"] == second.json()["controller_parameters"]

    listing = client.get(f"/api/v1/systems/{system_id}/optimizations")
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 2
    assert [item["run_id"] for item in body["items"]] == [
        second.json()["run_id"],
        first.json()["run_id"],
    ]
    assert body["items"][0]["summary"]["mse"] == pytest.approx(
        second.json()["achieved_metrics"]["mse"]
    )


def test_optimize_rejects_invalid_ranges(client: TestClient):
    system_id = _create_ball_beam(client)

    response = client.post(
        f"/api/v1/systems/{system_id}/optimize",
        json=_optimize_payload(param_ranges={"Kp": [10.0, 1.0]}),
    )

    assert response.status_code == 422


def test_optimize_rejects_async_until_phase_7(client: TestClient):
    system_id = _create_ball_beam(client)

    response = client.post(
        f"/api/v1/systems/{system_id}/optimize",
        json=_optimize_payload(**{"async": True}),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_parameters"


def test_optimize_requires_capability(client: TestClient):
    created = client.post(
        "/api/v1/systems",
        json={
            "source": {
                "type": "python_code",
                "code": "def dynamics(t, x, u):\n    return x\n",
                "metadata": {"name": "simulate-only"},
            }
        },
    )
    assert created.status_code == 201, created.text
    system_id = created.json()["system_id"]

    response = client.post(f"/api/v1/systems/{system_id}/optimize", json=_optimize_payload())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "capability_not_supported"


def test_optimization_history_404_and_delete(client: TestClient):
    missing = client.get("/api/v1/optimizations/not-a-uuid")
    assert missing.status_code == 404

    system_id = _create_ball_beam(client)
    created = client.post(f"/api/v1/systems/{system_id}/optimize", json=_optimize_payload())
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]

    deleted = client.delete(f"/api/v1/optimizations/{run_id}")
    assert deleted.status_code == 204

    assert client.get(f"/api/v1/optimizations/{run_id}").status_code == 404
    listing = client.get(f"/api/v1/systems/{system_id}/optimizations")
    assert listing.json()["total"] == 0


def test_deleting_system_cascades_optimization_runs(client: TestClient):
    system_id = _create_ball_beam(client)
    created = client.post(f"/api/v1/systems/{system_id}/optimize", json=_optimize_payload())
    assert created.status_code == 200, created.text

    deleted = client.delete(f"/api/v1/systems/{system_id}")
    assert deleted.status_code == 204

    assert client.get(f"/api/v1/optimizations/{created.json()['run_id']}").status_code == 404
