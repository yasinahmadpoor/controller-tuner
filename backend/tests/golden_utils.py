from __future__ import annotations

import hashlib
import json
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"

MANUAL_CASE_STUDY = REPO_ROOT / "engines" / "tunerPID" / "case_studies" / "BallBeam.py"
GA_CASE_STUDY = REPO_ROOT / "engines" / "gaTunerPID" / "case_studies" / "json" / "BallBeam.json"

MANUAL_INPUTS = {
    "case_study": "engines/tunerPID/case_studies/BallBeam.py",
    "num_inputs": 1,
    "controller_type": "PID",
    "params": {"Kp": 15.0, "Ki": 0.5, "Kd": 2.0},
    "fixed_initial_state": [1.0, 0.0],
    "simulation": {
        "dt": 0.01,
        "max_time": 1.0,
        "target": 0.0,
        "min_control": -0.5,
        "max_control": 0.5,
        "input_channel": 0,
        "output_channel": 0,
        "trim_values": [0.0],
    },
}

GA_INPUTS = {
    "case_study": "engines/gaTunerPID/case_studies/json/BallBeam.json",
    "ga_config": {"population_size": 5, "generations": 2, "seed": 42},
    "weights": {
        "mse": 1.0,
        "settling_time": 0.5,
        "overshoot": 0.5,
        "control_effort": 0.1,
    },
    "param_ranges": {
        "Kp": [1.0, 50.0],
        "Ki": [0.01, 5.0],
        "Kd": [0.01, 10.0],
    },
    "fixed_targets": {
        "mse": 0.05,
        "settling_time": 1.0,
        "overshoot": 1.0,
        "control_effort": 0.1,
    },
    "simulation_overrides": {"dt": 0.01, "max_time": 1.0},
}


def to_builtin(value: Any) -> Any:
    """Convert NumPy scalars/arrays into values accepted by json.dump."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    return value


def array_sha256(values: Any) -> str:
    array = np.asarray(values, dtype="<f8")
    return hashlib.sha256(array.tobytes()).hexdigest()


def series_summary(values: Any, *, edge: int = 5) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    return {
        "sha256": array_sha256(array),
        "length": int(array.size),
        "first": array[:edge].tolist(),
        "last": array[-edge:].tolist(),
    }


def _normalize_trim_values(value: Any, num_inputs: int) -> list[float]:
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, list):
        return [float(item) for item in value]
    return [0.0] * num_inputs


def load_ga_case_study() -> tuple[dict[str, Any], Any]:
    data = json.loads(GA_CASE_STUDY.read_text(encoding="utf-8"))
    module = types.ModuleType("ga_ballbeam_dynamics")
    code = compile(data["python_code"], str(GA_CASE_STUDY), "exec")
    exec(code, module.__dict__)
    if not hasattr(module, "dynamics"):
        raise RuntimeError(f"{GA_CASE_STUDY} does not define dynamics(t, x, u)")
    return data, module.dynamics


def build_manual_golden() -> dict[str, Any]:
    from app.engines.loader import manual

    engine = manual()
    system = engine["DynamicalSystem"](str(MANUAL_CASE_STUDY), num_inputs=1)

    sim_cfg = MANUAL_INPUTS["simulation"]
    system.dt = sim_cfg["dt"]
    system.max_time = sim_cfg["max_time"]
    system.target = sim_cfg["target"]
    system.min_control = sim_cfg["min_control"]
    system.max_control = sim_cfg["max_control"]
    system.input_channel = sim_cfg["input_channel"]
    system.output_channel = sim_cfg["output_channel"]
    system.trim_values = np.zeros(MANUAL_INPUTS["num_inputs"])

    simulator = engine["Simulator"](system)
    result = simulator.evaluate(
        MANUAL_INPUTS["controller_type"],
        MANUAL_INPUTS["params"],
        fixed_initial_state=MANUAL_INPUTS["fixed_initial_state"],
    )

    return {
        "description": "Manual engine BallBeam PID deterministic baseline",
        "inputs": MANUAL_INPUTS,
        "outputs": {
            "num_points": len(result["time_points"]),
            "time_points": series_summary(result["time_points"]),
            "trajectory": series_summary(result["trajectory"]),
            "control_signals": series_summary(result["control_signals"]),
            "metrics": to_builtin(result["metrics"]),
        },
    }


def build_ga_golden() -> dict[str, Any]:
    from app.engines.loader import ga

    data, dynamics = load_ga_case_study()
    num_inputs = int(data["num_inputs"])
    trim_values = _normalize_trim_values(data.get("trim_values", 0.0), num_inputs)
    trim_ics = data.get("trim_ics", [0.0] * int(data["num_states"]))

    system_config = {
        "dt": GA_INPUTS["simulation_overrides"]["dt"],
        "max_time": GA_INPUTS["simulation_overrides"]["max_time"],
        "target": float(data["target"]),
        "num_inputs": num_inputs,
        "input_channel": int(data["input_channel"]),
        "output_channel": int(data["output_channel"]),
        "min_ctrl": float(data["min_ctrl"]),
        "max_ctrl": float(data["max_ctrl"]),
        "trim_values": trim_values,
        "trim_ics": [float(value) for value in trim_ics],
        "num_states": int(data["num_states"]),
    }

    engine = ga()
    simulator = engine["SystemSimulator"](dynamics, system_config)
    optimizer = engine["GAOptimizer"](simulator, GA_INPUTS["ga_config"])
    result = optimizer.optimize_pid(
        weights=GA_INPUTS["weights"],
        param_ranges=GA_INPUTS["param_ranges"],
        fixed_targets=GA_INPUTS["fixed_targets"],
    )

    outputs = to_builtin(result)
    outputs["progress"].pop("cumulative_wall_time", None)
    outputs.pop("target_hit_time", None)

    return {
        "description": "GA engine BallBeam seeded smoke baseline",
        "inputs": {**GA_INPUTS, "system_config": system_config},
        "outputs": outputs,
    }


def dump_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=True) + "\n",
        encoding="utf-8",
    )
