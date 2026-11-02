"""GA auto-tuning engine adapter (Phase 4).

Builds a fresh ``SystemSimulator``/``GAOptimizer`` per request and normalizes
the engine result (NumPy values, NaN/Infinity progress) for JSON persistence
and API responses.

Contract note: the reference ``gaTunerPID/app.py`` calls
``optimize_pid(targets, weights, param_ranges)`` (targets first), while the
engine's public contract is
``optimize_pid(weights, param_ranges, fixed_targets)``. This adapter always
uses the keyword form so it is immune to the positional drift.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from app.core.json_safe import json_safe
from app.domain.models import Engine, SystemSpec
from app.engines.loader import ga, manual
from app.engines.manual_adapter import merge_simulation_defaults, normalize_metrics

_GAIN_KEYS = ("Kp", "Ki", "Kd")


def build_ga_sim_config(spec: SystemSpec, overrides: Any | None = None) -> dict[str, Any]:
    """Translate a canonical ``SystemSpec`` into the GA engine config."""
    simulation = merge_simulation_defaults(spec.simulation, overrides)
    trim_ics = simulation.trim_ics
    if trim_ics is None:
        trim_ics = [0.0] * spec.num_states
    return {
        "dt": float(simulation.dt),
        "max_time": float(simulation.max_time),
        "target": float(simulation.target),
        "num_states": int(spec.num_states),
        "num_inputs": int(spec.num_inputs),
        "input_channel": int(simulation.input_channel),
        "output_channel": int(simulation.output_channel),
        "min_ctrl": float(simulation.min_control),
        "max_ctrl": float(simulation.max_control),
        "trim_values": [float(value) for value in simulation.trim_values],
        "trim_ics": [float(value) for value in trim_ics],
    }


def load_dynamics_callable(spec: SystemSpec, code_path: str | Path) -> Any:
    """Load the persisted dynamics through the manual engine and expose the callable."""
    system = manual()["DynamicalSystem"](str(code_path), num_inputs=spec.num_inputs)
    dynamics = getattr(system, "_dynamics", None)
    if dynamics is None:
        dynamics = getattr(system, "dynamics", None)
    if dynamics is None:
        raise ValueError("manual engine did not expose a dynamics callable")
    return dynamics


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _merge_optimization_defaults(
    spec: SystemSpec, request: Any
) -> tuple[dict[str, list[float]], dict[str, float], dict[str, float], dict[str, Any]]:
    defaults = spec.optimization

    requested_ranges = getattr(request, "param_ranges", None)
    if requested_ranges is None and isinstance(request, dict):
        requested_ranges = request.get("param_ranges")
    ranges = dict(defaults.param_ranges)
    if requested_ranges:
        ranges.update(requested_ranges)

    requested_weights = getattr(request, "weights", None)
    if requested_weights is None and isinstance(request, dict):
        requested_weights = request.get("weights")
    weights = dict(defaults.weights)
    if requested_weights:
        weights.update(requested_weights)

    requested_targets = getattr(request, "fixed_targets", None)
    if requested_targets is None and isinstance(request, dict):
        requested_targets = request.get("fixed_targets")
    fixed_targets = dict(defaults.fixed_targets)
    if requested_targets:
        fixed_targets.update(requested_targets)

    requested_ga = getattr(request, "ga_config", None)
    if requested_ga is None and isinstance(request, dict):
        requested_ga = request.get("ga_config")
    if requested_ga is None:
        ga_config = dict(defaults.ga)
    elif hasattr(requested_ga, "model_dump"):
        ga_config = requested_ga.model_dump()
    else:
        ga_config = dict(requested_ga)

    param_ranges = {key: [float(value[0]), float(value[1])] for key, value in ranges.items()}
    return (
        param_ranges,
        {str(key): float(value) for key, value in weights.items()},
        {str(key): float(value) for key, value in fixed_targets.items()},
        {
            "population_size": int(ga_config.get("population_size", 20)),
            "generations": int(ga_config.get("generations", 30)),
            "seed": ga_config.get("seed"),
            "max_wall_clock": float(ga_config.get("max_wall_clock", 120.0)),
            "experiment_start_time": ga_config.get("experiment_start_time"),
            "nfe_offset": int(ga_config.get("nfe_offset", 0)),
        },
    )


def normalize_optimize_result(raw: Any) -> dict[str, Any]:
    """Convert an engine optimization result into a JSON-safe payload."""
    result = raw if isinstance(raw, dict) else {}
    metrics, non_finite = normalize_metrics(result.get("achieved_metrics"))

    target_hit = result.get("target_hit")
    if not isinstance(target_hit, dict):
        target_hit = {
            "nfe": result.get("target_hit_nfe"),
            "time": result.get("target_hit_time"),
            "generation": result.get("target_hit_generation"),
        }

    parameters = result.get("controller_parameters") or {}
    controller_parameters = {str(key): float(value) for key, value in parameters.items()}

    warnings = json_safe(result.get("warnings") or [])
    if not isinstance(warnings, list):
        warnings = [str(warnings)]

    return {
        "engine": Engine.GA.value,
        "success": bool(result.get("success", True)),
        "controller_parameters": controller_parameters,
        "achieved_metrics": metrics,
        "ga_cost": _float_or_none(result.get("ga_cost")),
        "baseline_cost": _float_or_none(result.get("baseline_cost")),
        "progress": json_safe(result.get("progress") or {}),
        "stop_reason": str(result.get("stop_reason") or "normal"),
        "num_evaluations": int(result.get("num_evaluations") or 0),
        "target_hit": json_safe(target_hit),
        "warnings": [str(warning) for warning in warnings],
        "non_finite_metrics": non_finite,
    }


class AutoTuneEngineAdapter:
    """Thin adapter over the read-only ``gaTunerPID`` engine."""

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
        raise ValueError("a code path is required to build the GA engine system")

    def optimize(
        self,
        spec: SystemSpec,
        request: Any | None = None,
        *,
        code_path: str | Path | None = None,
        overrides: Any | None = None,
    ) -> dict[str, Any]:
        param_ranges, weights, fixed_targets, ga_config = _merge_optimization_defaults(
            spec, request if request is not None else {}
        )
        if set(param_ranges) != set(_GAIN_KEYS):
            missing = sorted(set(_GAIN_KEYS) - set(param_ranges))
            raise ValueError(f"GA optimization requires ranges for {missing}")

        resolved = self._resolve_code_path(spec, code_path)
        dynamics = load_dynamics_callable(spec, resolved)
        simulator = ga()["SystemSimulator"](dynamics, build_ga_sim_config(spec, overrides))
        optimizer = ga()["GAOptimizer"](simulator, ga_config)
        raw = optimizer.optimize_pid(
            weights=weights,
            param_ranges=param_ranges,
            fixed_targets=fixed_targets,
        )
        return normalize_optimize_result(raw)


__all__ = [
    "AutoTuneEngineAdapter",
    "build_ga_sim_config",
    "load_dynamics_callable",
    "normalize_optimize_result",
]
