from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.api.schemas import (
    GAConfig,
    OptimizeRequest,
    RunType,
    SimulationOverrides,
    SystemResponse,
    TargetRange,
)


def _system_response_payload() -> dict:
    return {
        "system_id": str(uuid.uuid4()),
        "name": "Ball Beam",
        "source_type": "catalog_json",
        "source_ref": "ball_beam",
        "num_states": 2,
        "num_inputs": 1,
        "target": 0.0,
        "capabilities": ["simulate", "optimize"],
        "simulation": {
            "dt": 0.01,
            "max_time": 20.0,
            "target": 0.0,
            "min_control": -0.5,
            "max_control": 0.5,
            "input_channel": 0,
            "output_channel": 0,
            "trim_values": [0.0],
            "trim_ics": [1.0, 0.0],
        },
        "optimization": {
            "param_ranges": {"Kp": [1.0, 50.0], "Ki": [0.01, 5.0], "Kd": [0.01, 10.0]},
            "weights": {"mse": 1.0, "settling_time": 0.5, "overshoot": 0.5, "control_effort": 0.1},
            "fixed_targets": {
                "mse": 0.05,
                "settling_time": 1.0,
                "overshoot": 1.0,
                "control_effort": 0.1,
            },
            "ga": {"population_size": 20, "generations": 30, "seed": 42, "max_wall_clock": 120},
        },
        "created_at": datetime(2026, 1, 1).isoformat(),
    }


def test_system_response_roundtrip():
    response = SystemResponse.model_validate(_system_response_payload())
    assert response.num_states == 2
    assert response.source_type.value == "catalog_json"
    assert response.source_ref == "ball_beam"
    assert response.optimization.ga["population_size"] == 20
    assert [capability.value for capability in response.capabilities] == [
        "simulate",
        "optimize",
    ]


def test_ga_config_bounds():
    assert GAConfig(population_size=5, generations=1).population_size == 5
    with pytest.raises(ValidationError):
        GAConfig(population_size=4)
    with pytest.raises(ValidationError):
        GAConfig(generations=501)
    with pytest.raises(ValidationError):
        GAConfig(max_wall_clock=0)


def test_param_range_validation_rejects_inverted():
    with pytest.raises(ValidationError):
        OptimizeRequest(param_ranges={"Kp": [50.0, 1.0], "Ki": [0.01, 5.0], "Kd": [0.01, 10.0]})


def test_fixed_targets_must_be_positive():
    with pytest.raises(ValidationError):
        OptimizeRequest(fixed_targets={"mse": 0.0, "settling_time": 1.0})


def test_negative_weights_rejected():
    with pytest.raises(ValidationError):
        OptimizeRequest(
            weights={"mse": -1.0, "settling_time": 0.5, "overshoot": 0.5, "control_effort": 0.1}
        )


def test_negative_controllable_metric_key_rejected():
    with pytest.raises(ValidationError):
        OptimizeRequest(weights={"not_a_metric": 1.0})


def test_simulation_override_min_control_must_be_less_than_max():
    with pytest.raises(ValidationError):
        SimulationOverrides(min_control=10.0, max_control=-10.0)


def test_target_range_orders():
    assert TargetRange(min=0.0, max=5.0).min == 0.0
    with pytest.raises(ValidationError):
        TargetRange(min=5.0, max=0.0)


def test_run_type_enum_shape():
    assert RunType.SIMULATION.value == "simulation"
    assert RunType.OPTIMIZATION.value == "optimization"
