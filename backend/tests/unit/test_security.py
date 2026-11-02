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


@pytest.mark.parametrize(
    "module",
    [
        "os",
        "sys",
        "subprocess",
        "socket",
        "shutil",
        "pathlib",
        "importlib",
        "ctypes",
        "multiprocessing",
        "threading",
        "pickle",
        "marshal",
        "builtins",
    ],
)
def test_security_rejects_every_denylisted_import(module: str):
    code = f"import {module}\n\ndef dynamics(t, x, u):\n    return x\n"
    with pytest.raises(UnsafeImport):
        validate_python_source(code)


def test_security_rejects_import_from_and_relative_imports():
    with pytest.raises(UnsafeImport):
        validate_python_source(
            "from subprocess import run\n\ndef dynamics(t, x, u):\n    return x\n"
        )
    with pytest.raises(UnsafeImport):
        validate_python_source("from . import helper\n\ndef dynamics(t, x, u):\n    return x\n")


@pytest.mark.parametrize(
    "call",
    [
        "eval('1')",
        "exec('x = 1')",
        "compile('1', 'x', 'eval')",
        "open('/etc/passwd')",
        "input()",
        "__import__('os')",
        "breakpoint()",
        "exit()",
        "quit()",
        "globals()",
        "locals()",
        "vars()",
        "delattr(x, 'shape')",
        "setattr(x, 'shape', 1)",
        "getattr(x, 'shape')",
    ],
)
def test_security_rejects_every_dangerous_call(call: str):
    code = f"def dynamics(t, x, u):\n    {call}\n    return x\n"
    with pytest.raises(UnsafeImport):
        validate_python_source(code)


@pytest.mark.parametrize("expression", ["x.__class__", "x.__globals__", "__builtins__"])
def test_security_rejects_dunder_access(expression: str):
    code = f"def dynamics(t, x, u):\n    return {expression}\n"
    with pytest.raises(UnsafeImport):
        validate_python_source(code)


def test_security_rejects_module_scope_loop():
    code = """
for i in range(3):
    pass

def dynamics(t, x, u):
    return x
"""
    with pytest.raises(UnsafeImport):
        validate_python_source(code)


def test_security_allows_loops_inside_dynamics():
    code = """
def dynamics(t, x, u):
    total = 0
    for i in range(3):
        total += i
    while total > 1:
        total -= 1
    return x
"""
    validate_python_source(code)


def test_security_errors_do_not_leak_source_or_paths():
    code = "import os\n\ndef dynamics(t, x, u):\n    return x\n"
    with pytest.raises(UnsafeImport) as excinfo:
        validate_python_source(code)

    message = str(excinfo.value.message)
    assert "import os" not in message
    assert "/" not in message
