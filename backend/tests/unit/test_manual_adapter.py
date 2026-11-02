from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

import numpy as np
import pytest

from app.api.schemas import SimulateRequest, SimulationOverrides
from app.domain.models import (
    Capability,
    ControllerType,
    OptimizationDefaults,
    SimulationDefaults,
    SystemSource,
    SystemSpec,
)
from app.engines import manual_adapter
from app.engines.manual_adapter import ManualEngineAdapter, normalize_manual_result


class _FakeDynamicalSystem:
    instances: ClassVar[list[_FakeDynamicalSystem]] = []

    def __init__(self, path: str, num_inputs: int = 1):
        self.path = path
        self.num_inputs = num_inputs
        self.dt = None
        self.max_time = None
        self.target = None
        self.input_channel = None
        self.output_channel = None
        self.min_control = None
        self.max_control = None
        self.trim_values = None
        self.initial_condition_range = None
        self.randomness_level = None
        self.disturbance_level = None
        _FakeDynamicalSystem.instances.append(self)

    def get_param_schema(self, controller_type: str) -> dict:
        return {"Kp": {"min": 0.1, "max": 60.0}, "type": controller_type}


class _FakeSimulator:
    def __init__(self, system: _FakeDynamicalSystem):
        self.system = system
        self.fixed_initial_state = None

    def evaluate(self, controller_type, params, fixed_initial_state=None):
        assert controller_type == "PID"
        self.fixed_initial_state = fixed_initial_state
        return {
            "time_points": np.array([0.0, 0.01, 0.02]),
            "trajectory": np.array([1.0, 0.99, 0.98]),
            "control_signals": np.array([0.1, 0.2, 0.3]),
            "metrics": {
                "mse": np.float64(0.01),
                "settling_time": math.inf,
                "stable": False,
            },
        }


@pytest.fixture
def fake_engine(monkeypatch):
    _FakeDynamicalSystem.instances.clear()
    monkeypatch.setattr(
        manual_adapter,
        "manual",
        lambda: {"DynamicalSystem": _FakeDynamicalSystem, "Simulator": _FakeSimulator},
    )


def _spec(**simulation) -> SystemSpec:
    defaults = {
        "dt": 0.01,
        "max_time": 1.0,
        "target": 0.0,
        "min_control": -0.5,
        "max_control": 0.5,
    }
    defaults.update(simulation)
    return SystemSpec(
        system_id=uuid4(),
        name="BallBeam",
        source_type=SystemSource.CATALOG_JSON,
        num_states=2,
        num_inputs=1,
        capabilities=[Capability.SIMULATE],
        simulation=SimulationDefaults(**defaults),
        optimization=OptimizationDefaults(),
        code_sha256="0" * 64,
        code_size=10,
        created_at=datetime.now(UTC),
    )


def test_adapter_builds_system_and_normalizes_result(fake_engine, tmp_path: Path):
    code_path = tmp_path / "system.py"
    code_path.write_text("def dynamics(t, x, u):\n    return x\n", encoding="utf-8")
    request = SimulateRequest(
        controller_type=ControllerType.PID,
        params={"Kp": 15.0, "Ki": 0.5, "Kd": 2.0},
        initial_state=[1.0, 0.0],
    )

    result = ManualEngineAdapter().simulate(_spec(), request, code_path=code_path)

    system = _FakeDynamicalSystem.instances[-1]
    assert system.dt == 0.01
    assert system.max_time == 1.0
    assert system.min_control == -0.5
    assert system.max_control == 0.5
    assert result["engine"] == "manual_tuner"
    assert result["time_points"] == [0.0, 0.01, 0.02]
    assert result["trajectory"] == [1.0, 0.99, 0.98]
    assert result["metrics"]["mse"] == 0.01
    assert result["metrics"]["settling_time"] is None
    assert result["non_finite_metrics"] == ["settling_time"]


def test_adapter_applies_overrides_and_keeps_defaults(fake_engine, tmp_path: Path):
    code_path = tmp_path / "system.py"
    code_path.write_text("def dynamics(t, x, u):\n    return x\n", encoding="utf-8")
    request = SimulateRequest(
        controller_type=ControllerType.PID,
        params={"Kp": 1.0, "Ki": 1.0, "Kd": 1.0},
        initial_state=[0.0, 0.0],
        overrides=SimulationOverrides(max_time=2.5),
    )

    ManualEngineAdapter().simulate(_spec(), request, code_path=code_path)

    system = _FakeDynamicalSystem.instances[-1]
    assert system.max_time == 2.5
    assert system.dt == 0.01


def test_adapter_seeds_numpy_when_provided(fake_engine, tmp_path: Path, monkeypatch):
    code_path = tmp_path / "system.py"
    code_path.write_text("def dynamics(t, x, u):\n    return x\n", encoding="utf-8")
    seeds: list[int] = []
    monkeypatch.setattr(np.random, "seed", seeds.append)

    request = SimulateRequest(
        controller_type=ControllerType.PID,
        params={"Kp": 1.0, "Ki": 1.0, "Kd": 1.0},
        seed=42,
    )
    ManualEngineAdapter().simulate(_spec(), request, code_path=code_path)

    assert seeds == [42]


def test_schema_returns_engine_schema(fake_engine, tmp_path: Path):
    code_path = tmp_path / "system.py"
    code_path.write_text("def dynamics(t, x, u):\n    return x\n", encoding="utf-8")

    schema = ManualEngineAdapter().schema(_spec(), ControllerType.PID, code_path=code_path)

    assert schema["Kp"] == {"min": 0.1, "max": 60.0}
    assert schema["type"] == "PID"


def test_normalize_manual_result_replaces_non_finite_values():
    normalized = normalize_manual_result(
        {
            "time_points": np.array([0.0, 1.0]),
            "trajectory": np.array([1.0, 0.5]),
            "control_signals": np.array([0.0, 1.0]),
            "metrics": {"settling_time": -math.inf, "mse": np.float64(0.2)},
        }
    )

    assert normalized["metrics"]["settling_time"] is None
    assert normalized["metrics"]["mse"] == 0.2
    assert normalized["non_finite_metrics"] == ["settling_time"]
