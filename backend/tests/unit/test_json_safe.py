import json
import math
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import numpy as np

from app.core.json_safe import json_safe


def test_numpy_scalars_become_plain_python():
    assert json_safe(np.float64(1.0)) == 1.0
    assert json_safe(np.int32(3)) == 3
    assert json_safe(np.bool_(True)) is True


def test_float_infinity_and_nan_become_none():
    assert json_safe(float("inf")) is None
    assert json_safe(float("-inf")) is None
    assert json_safe(float("nan")) is None
    assert json_safe(np.float64(float("nan"))) is None
    assert json_safe(np.float64(float("inf"))) is None


def test_numpy_arrays_are_unwrapped():
    assert json_safe(np.array([1.0, 2.0, np.inf])) == [1.0, 2.0, None]
    assert json_safe(np.array([[1, 2], [3, 4]])) == [[1, 2], [3, 4]]


def test_nested_structures_are_recursed():
    payload = {
        "metrics": {"mse": np.float64(0.5), "bad": float("nan")},
        "trajectory": np.array([1.0, np.inf]),
        "warnings": ["a", "b"],
        "counts": (np.int64(1), np.int64(2)),
        "ids": {np.int64(7)},
    }
    cleaned = json_safe(payload)
    assert cleaned == {
        "metrics": {"mse": 0.5, "bad": None},
        "trajectory": [1.0, None],
        "warnings": ["a", "b"],
        "counts": [1, 2],
        "ids": [7],
    }


def test_scalars_and_dates_and_uuids_are_safe():
    now = datetime(2026, 1, 2, 3, 4, 5)
    assert json_safe(now) == "2026-01-02T03:04:05"
    assert json_safe(date(2026, 1, 2)) == "2026-01-02"
    assert json_safe(UUID("75d1f1a1-9332-4f2f-bd3a-6bdbe57b6b4d")) == (
        "75d1f1a1-9332-4f2f-bd3a-6bdbe57b6b4d"
    )
    assert json_safe(Decimal("1.25")) == 1.25
    assert json_safe(None) is None
    assert json_safe(True) is True
    assert json_safe(False) is False
    assert json_safe(7) == 7
    assert json_safe("hello") == "hello"


def test_bytes_decode_as_utf8():
    assert json_safe(b"hello") == "hello"


def test_result_is_json_encodable():
    payload = {
        "metrics": {"mse": np.float64(1.5), "settling_time": float("inf")},
        "trajectory": np.array([1.0, math.nan]),
    }
    cleaned = json_safe(payload)
    assert json.loads(json.dumps(cleaned)) == cleaned
