from __future__ import annotations

import os
import socket
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _wait_port(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def test_env() -> Iterator[None]:
    """Set env for the test Postgres/Redis pair, then yield."""
    previous = {
        key: os.environ.get(key)
        for key in (
            "DATABASE_URL",
            "REDIS_URL",
            "CELERY_BROKER_URL",
            "CELERY_RESULT_BACKEND",
        )
    }
    os.environ["DATABASE_URL"] = (
        "postgresql+psycopg://tuner:tuner@localhost:65432/controller_tuner_test"
    )
    os.environ["REDIS_URL"] = "redis://localhost:65433/0"
    os.environ["CELERY_BROKER_URL"] = "redis://localhost:65433/0"
    os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:65433/1"
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(scope="session")
def docker_dependency_stack() -> Iterator[None]:
    """Start test Postgres + Redis containers via docker compose, then tear down."""
    import subprocess

    if os.environ.get("TEST_SKIP_DOCKER_FIXTURES") == "1":
        yield
        return

    compose_file = Path(__file__).resolve().parents[2] / "docker" / "docker-compose.test.yml"
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d", "--wait"],
        check=True,
        capture_output=True,
    )
    try:
        yield
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down", "-v"],
            check=False,
            capture_output=True,
        )


@pytest.fixture(scope="session")
def ready_dependencies(docker_dependency_stack) -> Iterator[None]:
    """Wait for test Postgres and Redis to accept connections."""
    assert _wait_port("localhost", 65432), "test postgres did not come up"
    assert _wait_port("localhost", 65433), "test redis did not come up"
    yield
