from __future__ import annotations

import sys

from app.engines.loader import ga, load_engines, manual
from tests.golden_utils import REPO_ROOT


def test_both_engines_load_with_expected_exports():
    manual_engine = manual()
    ga_engine = ga()

    assert set(manual_engine) == {
        "DynamicalSystem",
        "Simulator",
        "MetricsCalculator",
    }
    assert set(ga_engine) == {
        "SystemSimulator",
        "GAOptimizer",
        "register_callback",
        "unregister_callback",
    }


def test_ga_repository_is_not_left_on_sys_path():
    load_engines()

    assert str((REPO_ROOT / "gaTunerPID").resolve()) not in sys.path
