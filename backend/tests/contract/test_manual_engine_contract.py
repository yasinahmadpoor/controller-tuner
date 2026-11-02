from __future__ import annotations

import json
import math

from tests.golden_utils import GOLDEN_DIR, build_manual_golden

GOLDEN_FILE = GOLDEN_DIR / "manual_ballbeam_pid.json"


def _assert_series(actual: dict, expected: dict) -> None:
    assert actual["length"] == expected["length"]
    assert actual["sha256"] == expected["sha256"]
    assert actual["first"] == expected["first"]
    assert actual["last"] == expected["last"]


def _assert_metrics(actual: dict, expected: dict) -> None:
    assert set(actual) == set(expected)
    for key, want in expected.items():
        got = actual[key]
        if isinstance(want, bool):
            assert got is want
        elif isinstance(want, float) and math.isinf(want):
            assert math.isinf(got) and (got > 0) == (want > 0)
        elif isinstance(want, float) and math.isnan(want):
            assert math.isnan(got)
        else:
            assert math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-12), key


def test_ballbeam_pid_matches_golden_baseline():
    expected = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["outputs"]
    actual = build_manual_golden()["outputs"]

    assert actual["num_points"] == expected["num_points"]
    _assert_series(actual["time_points"], expected["time_points"])
    _assert_series(actual["trajectory"], expected["trajectory"])
    _assert_series(actual["control_signals"], expected["control_signals"])
    _assert_metrics(actual["metrics"], expected["metrics"])
