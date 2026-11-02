"""Manual tuning engine adapter (Phase 3).

Builds a fresh ``DynamicalSystem`` per request so concurrent simulations never
share mutable engine state, then normalizes the engine output into plain
JSON-safe Python structures.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from app.core.json_safe import json_safe
from app.domain.models import ControllerType, Engine, SimulationDefaults, SystemSpec
from app.engines.loader import manual


def merge_simulation_defaults(
    defaults: SimulationDefaults, overrides: Any | None
) -> SimulationDefaults:
    """Overlay non-None request overrides onto the system's canonical defaults."""
    data = defaults.model_dump()
    if overrides is not None:
        values = overrides.model_dump() if hasattr(overrides, "model_dump") else dict(overrides)
        data.update({key: value for key, value in values.items() if value is not None})
    return SimulationDefaults.model_validate(data)


def build_manual_system(
    spec: SystemSpec,
    code_path: str | Path,
    overrides: Any | None = None,
) -> Any:
    """Construct a fully configured manual-engine ``DynamicalSystem``."""
    engine = manual()
    dynamics_cls = engine["DynamicalSystem"]
    system = dynamics_cls(str(code_path), num_inputs=spec.num_inputs)

    simulation = merge_simulation_defaults(spec.simulation, overrides)
    system.dt = float(simulation.dt)
    system.max_time = float(simulation.max_time)
    system.target = float(simulation.target)
    system.input_channel = int(simulation.input_channel)
    system.output_channel = int(simulation.output_channel)
    system.min_control = float(simulation.min_control)
    system.max_control = float(simulation.max_control)
    system.trim_values = np.asarray(simulation.trim_values, dtype=float)
    system.initial_condition_range = tuple(
        float(value) for value in simulation.initial_condition_range
    )
    system.randomness_level = float(simulation.randomness_level)
    system.disturbance_level = float(simulation.disturbance_level)
    return system


def _is_non_finite(value: Any) -> bool:
    if isinstance(value, (bool, int, str)) or value is None:
        return False
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def normalize_metrics(metrics: Any) -> tuple[dict[str, Any], list[str]]:
    """Return JSON-safe metrics plus the names of non-finite entries."""
    raw = metrics if isinstance(metrics, dict) else {}
    non_finite = [str(key) for key, value in raw.items() if _is_non_finite(value)]
    return json_safe(raw), non_finite


def normalize_manual_result(result: Any) -> dict[str, Any]:
    """Convert an engine simulation result into a JSON-safe adapter payload."""
    raw = result if isinstance(result, dict) else {}
    metrics, non_finite = normalize_metrics(raw.get("metrics"))
    return {
        "engine": Engine.MANUAL.value,
        "time_points": json_safe(list(raw.get("time_points", []))),
        "trajectory": json_safe(list(raw.get("trajectory", []))),
        "control_signals": json_safe(list(raw.get("control_signals", []))),
        "metrics": metrics,
        "non_finite_metrics": non_finite,
    }


class ManualEngineAdapter:
    """Thin adapter over the read-only ``tunerPID`` engine."""

    def __init__(
        self,
        code_path: str | Path | None = None,
        *,
        code_provider: Any | None = None,
    ):
        self._code_path = code_path
        self._code_provider = code_provider

    def _resolve_code_path(self, spec: SystemSpec, code_path: str | Path | None) -> str:
        if code_path is not None:
            return str(code_path)
        if self._code_path is not None:
            return str(self._code_path)
        if self._code_provider is not None:
            return str(self._code_provider(spec))
        raise ValueError("a code path is required to build the manual engine system")

    def build_system(
        self,
        spec: SystemSpec,
        *,
        overrides: Any | None = None,
        code_path: str | Path | None = None,
    ) -> Any:
        resolved = self._resolve_code_path(spec, code_path)
        return build_manual_system(spec, resolved, overrides)

    def schema(
        self,
        spec: SystemSpec,
        controller_type: ControllerType | str,
        *,
        code_path: str | Path | None = None,
    ) -> dict[str, Any]:
        controller = (
            controller_type
            if isinstance(controller_type, ControllerType)
            else ControllerType(str(controller_type))
        )
        system = self.build_system(spec, code_path=code_path)
        raw = system.get_param_schema(controller.value)
        return json_safe(raw)

    def get_param_schema(
        self,
        spec: SystemSpec,
        controller_type: ControllerType | str,
        *,
        code_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Alias matching the underlying engine method name."""
        return self.schema(spec, controller_type, code_path=code_path)

    def simulate(
        self,
        spec: SystemSpec,
        request: Any,
        *,
        code_path: str | Path | None = None,
    ) -> dict[str, Any]:
        controller_type = getattr(request, "controller_type", None)
        if controller_type is None and isinstance(request, dict):
            controller_type = request["controller_type"]
        controller = (
            controller_type
            if isinstance(controller_type, ControllerType)
            else ControllerType(str(controller_type))
        )

        params = getattr(request, "params", None)
        if params is None and isinstance(request, dict):
            params = request["params"]
        initial_state = getattr(request, "initial_state", None)
        if initial_state is None and isinstance(request, dict):
            initial_state = request.get("initial_state")
        overrides = getattr(request, "overrides", None)
        if overrides is None and isinstance(request, dict):
            overrides = request.get("overrides")
        seed = getattr(request, "seed", None)
        if seed is None and isinstance(request, dict):
            seed = request.get("seed")

        system = self.build_system(spec, overrides=overrides, code_path=code_path)
        if seed is not None:
            np.random.seed(int(seed))

        simulator = manual()["Simulator"](system)
        result = simulator.evaluate(
            controller.value,
            params,
            fixed_initial_state=initial_state,
        )
        return normalize_manual_result(result)


__all__ = [
    "ManualEngineAdapter",
    "build_manual_system",
    "merge_simulation_defaults",
    "normalize_manual_result",
    "normalize_metrics",
]
