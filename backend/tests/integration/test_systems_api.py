from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import reset_settings_cache
from app.db.models.artifact import ArtifactModel
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


def _upgrade_head(database_url: str) -> None:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_command.upgrade(cfg, "head")


def _truncate_tables(database_url: str) -> None:
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE systems, artifacts RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture
def client(ready_dependencies, test_env, monkeypatch, tmp_path):
    monkeypatch.setenv("ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("SYSTEM_TTL_SECONDS", "1")
    reset_settings_cache()
    _upgrade_head(os.environ["DATABASE_URL"])
    _truncate_tables(os.environ["DATABASE_URL"])

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    reset_settings_cache()


def test_catalog_endpoint_returns_curated_entries(client: TestClient):
    response = client.get("/api/v1/catalog")
    assert response.status_code == 200
    payload = response.json()
    ids = {item["catalog_id"] for item in payload["items"]}
    assert ids == {"ball_beam", "dc_motor", "inv_pendulum"}


def test_create_system_from_catalog_ball_beam(client: TestClient):
    response = client.post(
        "/api/v1/systems",
        json={"source": {"type": "catalog", "catalog_id": "ball_beam"}},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["num_states"] == 2
    assert payload["target"] == 0.0
    assert set(payload["capabilities"]) == {"simulate", "optimize"}


def test_create_case_study_json_matches_catalog_metadata(client: TestClient):
    catalog = client.post(
        "/api/v1/systems",
        json={"source": {"type": "catalog", "catalog_id": "ball_beam"}},
    )
    assert catalog.status_code == 201
    catalog_payload = catalog.json()

    case_study = json.loads(
        (REPO_ROOT / "gaTunerPID/case_studies/json/BallBeam.json").read_text(encoding="utf-8")
    )
    inline = client.post(
        "/api/v1/systems",
        json={"source": {"type": "case_study_json", "case_study": case_study}},
    )
    assert inline.status_code == 201, inline.text
    inline_payload = inline.json()
    for key in ("name", "num_states", "num_inputs", "target"):
        assert inline_payload[key] == catalog_payload[key]


def test_upload_python_file_with_metadata_creates_system(client: TestClient):
    code = (REPO_ROOT / "tunerPID/case_studies/BallBeam.py").read_text(encoding="utf-8")
    metadata = {
        "name": "Ball Beam Upload",
        "num_inputs": 1,
        "target": 0.0,
        "min_control": -0.5,
        "max_control": 0.5,
        "input_channel": 0,
        "output_channel": 0,
        "trim_values": [0.0],
        "trim_ics": [1.0, 0.0],
        "dt": 0.01,
        "max_time": 20.0,
    }
    response = client.post(
        "/api/v1/systems",
        files={"file": ("BallBeam.py", code, "text/x-python")},
        data={"metadata": json.dumps(metadata)},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["num_states"] == 2
    assert payload["name"] == "Ball Beam Upload"


def test_upload_with_unsafe_import_returns_error(client: TestClient):
    response = client.post(
        "/api/v1/systems",
        files={
            "file": (
                "bad.py",
                "import os\n\ndef dynamics(t, x, u):\n    return x\n",
                "text/x-python",
            )
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsafe_import"


def test_get_list_delete_system_hides_source_and_storage_fields(client: TestClient):
    created = client.post(
        "/api/v1/systems",
        json={"source": {"type": "catalog", "catalog_id": "dc_motor"}},
    )
    assert created.status_code == 201
    payload = created.json()
    system_id = payload["system_id"]

    fetched = client.get(f"/api/v1/systems/{system_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert "python_code" not in body
    assert "storage_key" not in body
    assert "artifact_path" not in body

    listed = client.get("/api/v1/systems", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    deleted = client.delete(f"/api/v1/systems/{system_id}")
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/systems/{system_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "system_not_found"


def test_uploading_identical_code_reuses_one_artifact_row(client: TestClient):
    code = "import numpy as np\n\ndef dynamics(t, x, u):\n    return np.array([x[1], -x[0] + u])\n"
    source = {"type": "python_code", "code": code, "metadata": {"name": "same"}}

    first = client.post("/api/v1/systems", json={"source": source})
    second = client.post("/api/v1/systems", json={"source": source})
    assert first.status_code == 201
    assert second.status_code == 201

    engine = client.app.state.context.engine
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        count = session.scalar(select(func.count()).select_from(ArtifactModel))
    assert count == 1


def test_expired_system_is_removed_by_cleanup_service(client: TestClient):
    response = client.post(
        "/api/v1/systems",
        json={
            "source": {
                "type": "python_code",
                "code": "import numpy as np\n\ndef dynamics(t, x, u):\n    return np.array([u])\n",
                "metadata": {"name": "ttl"},
            }
        },
    )
    assert response.status_code == 201
    system_id = response.json()["system_id"]

    service = client.app.state.context.system_service
    deleted = service.delete_expired(datetime.now(UTC) + timedelta(seconds=5))
    assert deleted >= 1

    missing = client.get(f"/api/v1/systems/{system_id}")
    assert missing.status_code == 404
