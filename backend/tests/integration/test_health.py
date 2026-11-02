"""Integration tests for /api/v1/health and /api/v1/ready.

Builds an AppContext with real test Postgres + Redis connections so readiness
probes report actual dependency health; each "down" test disables one
dependency to verify the readiness payload.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.api.middleware import REQUEST_ID_HEADER
from app.api.middleware import add_middleware as add_request_id_middleware
from app.api.v1 import health as health_router
from app.context import AppContext
from app.infrastructure.redis import RedisClients
from app.infrastructure.storage.local import LocalArtifactStorage

BACKEND_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = Path("/tmp/health-test-artifacts")


def _make_context() -> AppContext:
    context = AppContext(settings=None)
    fake_settings = type(
        "FakeSettings",
        (),
        {
            "app_env": "test",
            "log_level": "INFO",
            "artifact_dir": STORAGE_DIR,
            "cors_origin_list": [],
            "alembic_ini_path": BACKEND_ROOT / "alembic.ini",
            "alembic_dir": BACKEND_ROOT / "alembic",
            "ga_engine_repo": None,
            "manual_engine_repo": None,
        },
    )()
    context.settings = fake_settings
    context.engine = create_engine(os.environ["DATABASE_URL"])
    context.redis = RedisClients(type("R", (), {"redis_url": os.environ["REDIS_URL"]})())
    context.storage = LocalArtifactStorage(str(STORAGE_DIR))
    return context


@pytest.fixture
def app(ready_dependencies, test_env) -> FastAPI:
    context = _make_context()

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    alembic_command.upgrade(cfg, "head")

    context.engines_loaded = True

    built_app = FastAPI()
    built_app.state.context = context
    add_request_id_middleware(built_app)
    built_app.include_router(health_router.router, prefix="/api/v1")
    return built_app


@pytest.fixture
def client(app: FastAPI):
    yield TestClient(app)


def test_health_is_liveness_only(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_includes_request_id_header(client):
    response = client.get("/api/v1/health")
    assert REQUEST_ID_HEADER in response.headers
    assert response.headers[REQUEST_ID_HEADER]


def test_ready_returns_ready_when_everything_is_healthy(client):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert all(check["ok"] for check in payload["checks"].values())


def test_ready_reports_postgres_down(client):
    client.app.state.context.engine = None  # type: ignore[attr-defined]
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["postgres"]["ok"] is False


def test_ready_reports_redis_down(client):
    client.app.state.context.redis = None  # type: ignore[attr-defined]
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["redis"]["ok"] is False


def test_ready_reports_storage_down(client):
    client.app.state.context.storage = LocalArtifactStorage(  # type: ignore[attr-defined]
        "/proc/nonexistent-writable-path"
    )
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["checks"]["artifact_storage"]["ok"] is False


def test_ready_reports_engines_down(client):
    client.app.state.context.engines_loaded = False  # type: ignore[attr-defined]
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["engines"]["ok"] is False
