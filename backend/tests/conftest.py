from __future__ import annotations

from pathlib import Path

import pytest

from app.engines.loader import load_engines, reset_engines

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def loaded_engines():
    reset_engines()
    load_engines(
        ga_repo=REPO_ROOT / "gaTunerPID",
        manual_repo=REPO_ROOT / "tunerPID",
    )
    yield
    reset_engines()
