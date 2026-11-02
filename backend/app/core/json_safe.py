from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import numpy as np

_MISSING_VALUE = None


def _clean_float(value: float) -> float:
    return value if math.isfinite(value) else _MISSING_VALUE


def json_safe(value: Any) -> Any:
    """Convert a nested value into plain JSON-serializable Python data.

    NumPy scalars/arrays are unwrapped; non-finite floats (``NaN``,
    ``Infinity``, ``-Infinity``) become ``None`` so that Starlette's strict
    JSON encoder never rejects an engine payload.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value

    if isinstance(value, np.generic):
        return json_safe(value.item())

    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]

    if isinstance(value, float):
        return _clean_float(value)

    if isinstance(value, Decimal):
        cleaned = float(value)
        return _clean_float(cleaned)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    return str(value)
