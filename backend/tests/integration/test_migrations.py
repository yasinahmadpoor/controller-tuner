"""Alembic migration tests.

Run against the test-services Postgres (see tests/integration/conftest.py).
``alembic upgrade head`` must succeed on an empty schema; Phase 2 creates
``artifacts`` and ``systems`` in addition to ``alembic_version``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _read_current_head(database_url: str) -> tuple[str | None, str | None]:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    return current, head


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_empty_schema_upgrades_to_head(ready_dependencies, test_env):
    database_url = os.environ["DATABASE_URL"]
    _run_alembic("downgrade", "base")

    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr

    current, head = _read_current_head(database_url)
    assert current == head, "migrations did not reach head"


def test_database_schema_has_only_alembic_version_table(ready_dependencies, test_env):
    engine = create_engine(os.environ["DATABASE_URL"])
    tables = inspect(engine).get_table_names()
    assert set(tables) == {"alembic_version", "artifacts", "systems", "simulation_runs"}


def test_migration_roundtrip_is_reversible(ready_dependencies, test_env):
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO alembic_version (version_num) VALUES ('0001_baseline') "
                "ON CONFLICT (version_num) DO UPDATE SET version_num = EXCLUDED.version_num"
            )
        )

    assert _run_alembic("downgrade", "base").returncode == 0
    assert _run_alembic("upgrade", "head").returncode == 0

    tables = inspect(engine).get_table_names()
    assert "alembic_version" in tables


def test_upgrade_followed_by_migration_state(clean_database, test_env):
    assert _run_alembic("upgrade", "head").returncode == 0
    engine = create_engine(os.environ["DATABASE_URL"])
    tables = inspect(engine).get_table_names()
    assert set(tables) == {"alembic_version", "artifacts", "systems", "simulation_runs"}
    current, head = _read_current_head(os.environ["DATABASE_URL"])
    assert current == head


@pytest.fixture
def clean_database(ready_dependencies, test_env):
    """Force the schema to base so each migration test starts from scratch."""
    _run_alembic("downgrade", "base")
    yield
