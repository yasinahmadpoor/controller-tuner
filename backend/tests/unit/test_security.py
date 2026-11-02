from __future__ import annotations

import pytest

from app.core.errors import InvalidPython, PayloadTooLarge, UnsafeImport
from app.core.security import validate_python_source


def test_security_accepts_valid_dynamics_code():
    code = """
import numpy as np

def dynamics(t, x, u):
    return np.array([x[1], -0.1 * x[0] + u])
"""
    validate_python_source(code, max_bytes=10_000)


def test_security_rejects_unsafe_import():
    code = """
import os

def dynamics(t, x, u):
    return x
"""
    with pytest.raises(UnsafeImport):
        validate_python_source(code)


def test_security_rejects_missing_dynamics_function():
    code = """
def not_dynamics(t, x, u):
    return x
"""
    with pytest.raises(InvalidPython):
        validate_python_source(code)


def test_security_rejects_while_true_loop():
    code = """
def dynamics(t, x, u):
    while True:
        return x
"""
    with pytest.raises(UnsafeImport):
        validate_python_source(code)


def test_security_rejects_payload_too_large():
    code = "def dynamics(t, x, u):\n    return x\n"
    with pytest.raises(PayloadTooLarge):
        validate_python_source(code * 1000, max_bytes=200)
