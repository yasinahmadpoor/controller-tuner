from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from tests.golden_utils import GOLDEN_DIR, build_ga_golden

GOLDEN_FILE = GOLDEN_DIR / "ga_ballbeam_p5_g2_s42.json"


def _assert_nested_close(actual: Any, expected: Any, path: str = "$") -> None:
    if isinstance(expected, Mapping):
        assert isinstance(actual, Mapping), path
        assert set(actual) == set(expected), path
        for key in expected:
            _assert_nested_close(actual[key], expected[key], f"{path}.{key}")
        return

    if isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), path
        for index, (got, want) in enumerate(zip(actual, expected, strict=True)):
            _assert_nested_close(got, want, f"{path}[{index}]")
        return

    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        assert actual == expected, path
        return

    if isinstance(expected, (int, float)):
        if isinstance(expected, float) and math.isnan(expected):
            assert math.isnan(actual), path
        elif isinstance(expected, float) and math.isinf(expected):
            assert math.isinf(actual) and (actual > 0) == (expected > 0), path
        else:
            assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12), path
        return

    raise AssertionError(f"Unsupported fixture value at {path}: {type(expected)!r}")


def test_ballbeam_ga_matches_seeded_golden_baseline():
    expected = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["outputs"]
    actual = build_ga_golden()["outputs"]

    _assert_nested_close(actual, expected)


def test_ga_optimizer_exposes_documented_optimize_pid_parameter_order():
    import inspect

    from app.engines.loader import ga, load_engines

    load_engines()
    signature = inspect.signature(ga()["GAOptimizer"].optimize_pid)

    assert list(signature.parameters) == [
        "self",
        "weights",
        "param_ranges",
        "fixed_targets",
    ]
