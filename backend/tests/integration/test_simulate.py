"""Integration tests for the Phase 3 manual simulation workflow."""

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
from app.db.models.simulation_run import SimulationRunModel
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
            text("TRUNCATE TABLE simulation_runs, systems, artifacts RESTART IDENTITY CASCADE")
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


def _pid_payload() -> dict:
    return {
        "controller_type": "PID",
        "params": {"Kp": 15.0, "Ki": 0.5, "Kd": 2.0},
        "initial_state": [1.0, 0.0],
        "overrides": {"dt": 0.01, "max_time": 1.0},
    }


def test_pid_schema_returns_all_gain_bounds(client: TestClient):
    system_id = _create_ball_beam(client)

    response = client.get(f"/api/v1/systems/{system_id}/schema", params={"controller_type": "PID"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["controller_type"] == "PID"
    assert set(payload["params"]) == {"Kp", "Ki", "Kd"}
    for bounds in payload["params"].values():
        assert bounds["min"] < bounds["max"]


def test_fsf_schema_returns_one_gain_per_state(client: TestClient):
    system_id = _create_ball_beam(client)

    response = client.get(f"/api/v1/systems/{system_id}/schema", params={"controller_type": "FSF"})

    assert response.status_code == 200, response.text
    assert set(response.json()["params"]) == {"K1", "K2"}


def test_simulate_persists_run_and_serializes_non_finite_metrics(client: TestClient):
    system_id = _create_ball_beam(client)

    response = client.post(f"/api/v1/systems/{system_id}/simulate", json=_pid_payload())

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["engine"] == "manual_tuner"
    assert payload["controller_type"] == "PID"
    assert payload["run_id"]
    assert len(payload["time_points"]) == len(payload["trajectory"])
    assert len(payload["time_points"]) == len(payload["control_signals"])
    assert payload["metrics"]["settling_time"] is None
    assert "settling_time" in payload["non_finite_metrics"]

    detail = client.get(f"/api/v1/simulations/{payload['run_id']}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["run_id"] == payload["run_id"]
    assert body["system_id"] == system_id
    assert body["params"] == _pid_payload()["params"]

    engine = client.app.state.context.engine
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(SimulationRunModel)) == 1


def test_simulation_history_list_and_delete(client: TestClient):
    system_id = _create_ball_beam(client)
    first = client.post(f"/api/v1/systems/{system_id}/simulate", json=_pid_payload())
    second = client.post(f"/api/v1/systems/{system_id}/simulate", json=_pid_payload())
    assert first.status_code == 200 and second.status_code == 200

    listing = client.get(f"/api/v1/systems/{system_id}/simulations")
    assert listing.status_code == 200
    assert listing.json()["total"] == 2

    run_id = first.json()["run_id"]
    deleted = client.delete(f"/api/v1/simulations/{run_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/simulations/{run_id}").status_code == 404

    listing = client.get(f"/api/v1/systems/{system_id}/simulations")
    assert listing.json()["total"] == 1


def test_deleting_system_cascades_to_simulation_runs(client: TestClient):
    system_id = _create_ball_beam(client)
    run_id = client.post(f"/api/v1/systems/{system_id}/simulate", json=_pid_payload()).json()[
        "run_id"
    ]

    assert client.delete(f"/api/v1/systems/{system_id}").status_code == 204
    assert client.get(f"/api/v1/simulations/{run_id}").status_code == 404


def test_invalid_controller_parameters_are_rejected(client: TestClient):
    system_id = _create_ball_beam(client)
    payload = _pid_payload()
    payload["params"] = {"Kp": 15.0, "Ki": 0.5}

    response = client.post(f"/api/v1/systems/{system_id}/simulate", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_parameters"


def test_fsf_requires_all_state_gains(client: TestClient):
    system_id = _create_ball_beam(client)

    response = client.post(
        f"/api/v1/systems/{system_id}/simulate",
        json={
            "controller_type": "FSF",
            "params": {"K1": 1.0},
            "initial_state": [1.0, 0.0],
            "overrides": {"max_time": 0.1},
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_parameters"


def test_unknown_system_returns_404(client: TestClient):
    response = client.get(
        "/api/v1/systems/00000000-0000-0000-0000-000000000000/schema",
        params={"controller_type": "PID"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "system_not_found"


def test_invalid_controller_type_returns_422(client: TestClient):
    system_id = _create_ball_beam(client)

    response = client.post(
        f"/api/v1/systems/{system_id}/simulate",
        json={
            "controller_type": "NOT_A_CONTROLLER",
            "params": {"Kp": 1.0},
        },
    )

    assert response.status_code == 422


def test_persist_trajectories_writes_artifact(ready_dependencies, test_env, monkeypatch, tmp_path):
    monkeypatch.setenv("ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("PERSIST_TRAJECTORIES", "true")
    reset_settings_cache()
    _upgrade_head(os.environ["DATABASE_URL"])
    _truncate_tables(os.environ["DATABASE_URL"])

    app = create_app()
    with TestClient(app) as client:
        system_id = _create_ball_beam(client)
        run_id = client.post(f"/api/v1/systems/{system_id}/simulate", json=_pid_payload()).json()[
            "run_id"
        ]

        detail = client.get(f"/api/v1/simulations/{run_id}", params={"include_artifacts": "true"})
        assert detail.status_code == 200
        body = detail.json()
        assert body["trajectory_artifact_id"] is not None
        assert body["trajectory"]["time_points"]
        assert len(body["trajectory"]["trajectory"]) == len(body["trajectory"]["time_points"])
    reset_settings_cache()
