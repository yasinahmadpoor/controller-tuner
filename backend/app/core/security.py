"""Static security validation for user-provided Python dynamics code.

Rules (docs/ARCHITECTURE.md §6.6 upload validation):
- code must parse (AST) and define a top-level ``dynamics(t, x, u)`` function;
- imports are restricted to an allowlist (``numpy``, ``math``);
- dangerous builtins/calls, dunder attribute access, and ``while True`` loops
  are rejected;
- errors are expressed with canonical domain errors carrying non-leaking
  messages (no filesystem paths, no raw snippets).
"""

from __future__ import annotations

import ast

from app.core.errors import InvalidPython, PayloadTooLarge, UnsafeImport

ALLOWED_IMPORT_ROOTS = frozenset({"numpy", "math"})

_REQUIRED_FUNCTION = "dynamics"

_DANGEROUS_CALLS = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "__import__",
        "breakpoint",
        "exit",
        "quit",
        "globals",
        "locals",
        "vars",
        "delattr",
        "setattr",
        "getattr",
    }
)

_MAX_STATES = 10


def validate_python_source(
    code: str,
    *,
    max_bytes: int | None = None,
    max_states: int = _MAX_STATES,
) -> None:
    """Validate user Python source for use as a dynamics module.

    Raises canonical domain errors; returns silently when the code is safe.
    """
    if max_bytes is not None:
        size = len(code.encode("utf-8"))
        if size > max_bytes:
            raise PayloadTooLarge(
                "code exceeds the maximum allowed size",
                context={"max_bytes": max_bytes, "actual_bytes": size},
            )

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise InvalidPython(
            "code is not valid Python",
            context={"line": exc.lineno},
        ) from exc

    _check_dunder_access(tree)
    _check_imports(tree)
    _check_calls(tree)
    _check_loops(tree)
    _check_module_scope_loops(tree)
    _check_dynamics_function(tree)


def _check_dunder_access(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafeImport("dunder attribute access is not allowed")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise UnsafeImport("dunder name access is not allowed")


def _check_imports(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        match node:
            case ast.Import():
                for alias in node.names:
                    _allow_root(alias.name)
            case ast.ImportFrom():
                if node.level:
                    raise UnsafeImport("relative imports are not allowed")
                if node.module:
                    _allow_root(node.module)


def _allow_root(module: str) -> None:
    root = module.split(".")[0]
    if root not in ALLOWED_IMPORT_ROOTS:
        raise UnsafeImport(
            f"import of module {module!r} is not allowed",
            context={"module": module, "allowed": sorted(ALLOWED_IMPORT_ROOTS)},
        )


def _check_calls(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        match node.func:
            case ast.Name(id=name) if name in _DANGEROUS_CALLS:
                raise UnsafeImport(f"call to {name!r} is not allowed")
            case ast.Attribute(attr=attr) if attr in _DANGEROUS_CALLS:
                raise UnsafeImport(f"call to {attr!r} is not allowed")


def _check_loops(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.While) and _is_constant_true(node.test):
            raise UnsafeImport("'while True' loops are not allowed")


def _check_module_scope_loops(tree: ast.AST) -> None:
    for node in tree.body:
        if isinstance(node, ast.For | ast.AsyncFor | ast.While):
            raise UnsafeImport("loops at module import scope are not allowed")


def _is_constant_true(test: ast.expr) -> bool:
    try:
        return bool(ast.literal_eval(test))
    except (ValueError, TypeError):
        return False


def _check_dynamics_function(tree: ast.AST) -> None:
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name == _REQUIRED_FUNCTION:
            _check_dynamics_signature(node)
            return
    raise InvalidPython("code must define a top-level 'dynamics(t, x, u)' function")


def _check_dynamics_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
    args = node.args
    names = [arg.arg for arg in args.posonlyargs + args.args]
    if len(names) == 3 and args.vararg is None and args.kwarg is None:
        return
    raise InvalidPython(
        "'dynamics' must accept exactly three positional parameters (t, x, u)",
        context={"params": names},
    )
