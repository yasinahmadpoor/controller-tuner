from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

import numpy as np
import pytest

from app.api.schemas import GAConfig, OptimizeRequest
from app.domain.models import (
    Capability,
    OptimizationDefaults,
    SimulationDefaults,
    SystemSource,
    SystemSpec,
)
from app.engines import auto_tune_adapter
from app.engines.auto_tune_adapter import (
    AutoTuneEngineAdapter,
    build_ga_sim_config,
    normalize_optimize_result,
)


class _FakeDynamicalSystem:
    def __init__(self, path: str, num_inputs: int = 1):
        self.path = path
        self.num_inputs = num_inputs
        self._dynamics = lambda t, x, u: x


class _FakeGAOptimizer:
    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, simulator: Any, config: dict[str, Any]):
        self.simulator = simulator
        self.config = config

    def optimize_pid(self, **kwargs: Any) -> dict[str, Any]:
        _FakeGAOptimizer.calls.append(kwargs)
        return {
            "success": True,
            "controller_parameters": {"Kp": np.float64(12.5), "Ki": 0.4, "Kd": 3.1},
            "achieved_metrics": {
                "mse": np.float64(0.03),
                "settling_time": math.inf,
                "overshoot": 0.7,
                "control_effort": np.float64(0.08),
            },
            "ga_cost": np.float64(0.21),
            "baseline_cost": math.inf,
            "progress": {
                "iteration": [1],
                "mean_baseline_cost": [np.nan],
                "Kp": [np.float64(12.5)],
            },
            "stop_reason": "normal",
            "num_evaluations": np.int64(16),
            "target_hit_nfe": None,
            "target_hit_time": None,
            "target_hit_generation": None,
            "warnings": [],
        }


@pytest.fixture
def fake_engine(monkeypatch):
    _FakeGAOptimizer.calls.clear()
    monkeypatch.setattr(
        auto_tune_adapter,
        "manual",
        lambda: {"DynamicalSystem": _FakeDynamicalSystem},
    )
    monkeypatch.setattr(
        auto_tune_adapter,
        "ga",
        lambda: {
            "SystemSimulator": lambda dynamics, config: object(),
            "GAOptimizer": _FakeGAOptimizer,
        },
    )


def _spec(**simulation) -> SystemSpec:
    defaults = {
        "dt": 0.01,
        "max_time": 1.0,
        "target": 0.0,
        "min_control": -0.5,
        "max_control": 0.5,
        "trim_values": [0.0],
        "trim_ics": [1.0, 0.0],
    }
    defaults.update(simulation)
    return SystemSpec(
        system_id=uuid4(),
        name="BallBeam",
        source_type=SystemSource.CATALOG_JSON,
        num_states=2,
        num_inputs=1,
        capabilities=[Capability.SIMULATE, Capability.OPTIMIZE],
        simulation=SimulationDefaults(**defaults),
        optimization=OptimizationDefaults(),
        code_sha256="0" * 64,
        code_size=10,
        created_at=datetime.now(UTC),
    )


def test_ga_config_maps_spec_fields_and_trim_defaults():
    config = build_ga_sim_config(_spec())

    assert config == {
        "dt": 0.01,
        "max_time": 1.0,
        "target": 0.0,
        "num_states": 2,
        "num_inputs": 1,
        "input_channel": 0,
        "output_channel": 0,
        "min_ctrl": -0.5,
        "max_ctrl": 0.5,
        "trim_values": [0.0],
        "trim_ics": [1.0, 0.0],
    }


def test_adapter_calls_engine_with_documented_keyword_order(fake_engine, tmp_path: Path):
    code_path = tmp_path / "system.py"
    code_path.write_text("def dynamics(t, x, u):\n    return x\n", encoding="utf-8")
    request = OptimizeRequest(
        param_ranges={"Kp": [1.0, 50.0], "Ki": [0.01, 5.0], "Kd": [0.01, 10.0]},
        weights={"mse": 1.0, "settling_time": 0.5, "overshoot": 0.5, "control_effort": 0.1},
        fixed_targets={"mse": 0.05, "settling_time": 1.0, "overshoot": 1.0, "control_effort": 0.1},
        ga_config=GAConfig(population_size=5, generations=2, seed=42, max_wall_clock=30),
    )

    AutoTuneEngineAdapter().optimize(_spec(), request, code_path=code_path)

    call = _FakeGAOptimizer.calls[-1]
    assert set(call) == {"weights", "param_ranges", "fixed_targets"}
    assert call["param_ranges"] == {
        "Kp": [1.0, 50.0],
        "Ki": [0.01, 5.0],
        "Kd": [0.01, 10.0],
    }
    assert call["weights"]["mse"] == 1.0
    assert call["fixed_targets"]["mse"] == 0.05


def test_adapter_normalizes_numpy_and_non_finite_values(fake_engine, tmp_path: Path):
    code_path = tmp_path / "system.py"
    code_path.write_text("def dynamics(t, x, u):\n    return x\n", encoding="utf-8")

    result = AutoTuneEngineAdapter().optimize(
        _spec(),
        OptimizeRequest(
            ga_config=GAConfig(population_size=5, generations=1, seed=42),
        ),
        code_path=code_path,
    )

    assert result["engine"] == "ga_tuner"
    assert result["controller_parameters"] == {"Kp": 12.5, "Ki": 0.4, "Kd": 3.1}
    assert result["achieved_metrics"]["settling_time"] is None
    assert result["non_finite_metrics"] == ["settling_time"]
    assert result["ga_cost"] == 0.21
    assert result["baseline_cost"] is None
    assert result["num_evaluations"] == 16
    assert result["progress"]["mean_baseline_cost"] == [None]
    assert result["target_hit"] == {"nfe": None, "time": None, "generation": None}


def test_normalize_optimize_result_accepts_target_hit_dict():
    result = normalize_optimize_result(
        {
            "success": True,
            "controller_parameters": {"Kp": 1.0, "Ki": 2.0, "Kd": 3.0},
            "achieved_metrics": {"mse": 0.1},
            "progress": {},
            "stop_reason": "score_100",
            "num_evaluations": 40,
            "target_hit": {"nfe": 40, "time": 1.5, "generation": 3},
            "warnings": [],
        }
    )

    assert result["target_hit"] == {"nfe": 40, "time": 1.5, "generation": 3}
    assert result["stop_reason"] == "score_100"
    assert result["controller_parameters"]["Kp"] == 1.0
