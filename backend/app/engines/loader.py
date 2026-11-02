from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import threading
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any


class EngineLoadError(RuntimeError):
    """Raised when one of the read-only engine packages cannot be loaded."""


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_GA_REPO = _REPO_ROOT / "gaTunerPID"
_DEFAULT_MANUAL_REPO = _REPO_ROOT / "tunerPID"

_lock = threading.RLock()
_manual: dict[str, Any] = {}
_ga: dict[str, Any] = {}


class _LoaderState:
    def __init__(self) -> None:
        self.loaded = False
        self.paths: tuple[Path, Path] | None = None


_state = _LoaderState()


def _resolve_repo(explicit: str | Path | None, env_var: str, default: Path) -> Path:
    raw = explicit if explicit is not None else os.environ.get(env_var, default)
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise EngineLoadError(f"Engine repository does not exist: {path}")
    return path


def _load_manual(repo: Path) -> None:
    package_dir = repo / "src"
    init_file = package_dir / "__init__.py"
    if not init_file.is_file():
        raise EngineLoadError(f"Manual engine package not found: {init_file}")

    try:
        spec = importlib.util.spec_from_file_location(
            "manual_engine",
            init_file,
            submodule_search_locations=[str(package_dir)],
        )
        if spec is None or spec.loader is None:
            raise EngineLoadError(f"Cannot build import spec for {init_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules["manual_engine"] = module
        spec.loader.exec_module(module)

        com = importlib.import_module("manual_engine.core")
        _manual.update(
            DynamicalSystem=com.DynamicalSystem,
            Simulator=com.Simulator,
            MetricsCalculator=com.MetricsCalculator,
        )
    except EngineLoadError:
        sys.modules.pop("manual_engine", None)
        raise
    except Exception as exc:
        sys.modules.pop("manual_engine", None)
        raise EngineLoadError(f"Failed to load manual engine from {repo}") from exc


def _load_ga(repo: Path) -> None:
    if not (repo / "src").is_dir():
        raise EngineLoadError(f"GA engine package not found: {repo / 'src'}")

    repo_str = str(repo)
    sys.path.insert(0, repo_str)
    try:
        simulator = importlib.import_module("src.simulator")
        optimizer = importlib.import_module("src.ga_optimizer")
        callbacks = importlib.import_module("src.callbacks")
        _ga.update(
            SystemSimulator=simulator.SystemSimulator,
            GAOptimizer=optimizer.GAOptimizer,
            register_callback=callbacks.register_callback,
            unregister_callback=callbacks.unregister_callback,
        )
    except Exception as exc:
        raise EngineLoadError(f"Failed to load GA engine from {repo}") from exc
    finally:
        try:
            sys.path.remove(repo_str)
        except ValueError:
            pass


def load_engines(
    ga_repo: str | Path | None = None,
    manual_repo: str | Path | None = None,
    *,
    force: bool = False,
) -> None:
    """Import both read-only engines once, preserving their import contracts."""
    with _lock:
        ga_path = _resolve_repo(ga_repo, "GA_ENGINE_REPO", _DEFAULT_GA_REPO)
        manual_path = _resolve_repo(manual_repo, "MANUAL_ENGINE_REPO", _DEFAULT_MANUAL_REPO)
        paths = (ga_path, manual_path)

        if _state.loaded and not force and _state.paths == paths:
            return
        if force:
            reset_engines()

        _load_manual(manual_path)
        _load_ga(ga_path)
        _state.paths = paths
        _state.loaded = True


def _ensure_loaded() -> None:
    load_engines()


def manual() -> Mapping[str, Any]:
    """Return the loaded manual engine classes."""
    _ensure_loaded()
    return MappingProxyType(_manual)


def ga() -> Mapping[str, Any]:
    """Return the loaded GA engine classes and callback helpers."""
    _ensure_loaded()
    return MappingProxyType(_ga)


def reset_engines() -> None:
    """Clear loaded modules. Intended for tests and isolated tooling."""
    with _lock:
        _manual.clear()
        _ga.clear()
        _state.loaded = False
        _state.paths = None

        for name in list(sys.modules):
            if name == "manual_engine" or name.startswith("manual_engine."):
                sys.modules.pop(name, None)
            if name == "src" or name.startswith("src."):
                sys.modules.pop(name, None)


def load_dynamics_from_code(code: str, num_inputs: int = 1) -> Any:
    """Materialize user ``dynamics`` code to a temp file and load it via the
    manual engine.

    The manual engine auto-detects ``num_states`` by probing the function;
    this is the canonical way to validate and introspect uploaded code.
    Returns the ``DynamicalSystem`` instance (engine-managed lifetime).
    """
    import tempfile

    com = manual()
    DynamicalSystem = com["DynamicalSystem"]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    try:
        return DynamicalSystem(tmp_path, num_inputs=num_inputs)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
