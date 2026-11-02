from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.models import (
    Capability,
    ControllerType,
    Engine,
    JobStatus,
    OptimizationDefaults,
    RunType,
    SimulationDefaults,
    SystemSource,
)


def test_enums_shape():
    assert list(ControllerType) == ["P", "PI", "PD", "PID", "FSF"]
    assert Engine.MANUAL.value == "manual_tuner"
    assert Engine.GA.value == "ga_tuner"
    assert [run_type.value for run_type in RunType] == ["simulation", "optimization"]
    assert list(JobStatus) == ["queued", "running", "succeeded", "failed", "cancelled"]
    assert [capability.value for capability in Capability] == ["simulate", "optimize"]
    assert [s.value for s in SystemSource] == [
        "catalog_json",
        "catalog_py",
        "uploaded_py",
        "inline_json",
        "inline_code",
    ]


def test_simulation_defaults_roundtrip():
    defaults = SimulationDefaults()
    dump = defaults.model_dump()
    assert SimulationDefaults.model_validate(dump) == defaults


def test_optimization_defaults_schema_is_canonical():
    defaults = OptimizationDefaults()
    assert defaults.param_ranges == {"Kp": (1.0, 50.0), "Ki": (0.01, 5.0), "Kd": (0.01, 10.0)}
    assert defaults.weights["mse"] == 1.0
    assert defaults.fixed_targets["settling_time"] == 3.0
    assert defaults.ga["population_size"] == 20
    assert defaults.ga["seed"] == 42


def test_system_spec_is_frozen():
    import uuid
    from datetime import datetime

    from app.domain.models import Capability, SystemSource, SystemSpec

    spec = SystemSpec(
        system_id=uuid.uuid4(),
        name="Ball Beam",
        source_type=SystemSource.CATALOG_JSON,
        num_states=2,
        num_inputs=1,
        capabilities=[Capability.SIMULATE, Capability.OPTIMIZE],
        simulation=SimulationDefaults(),
        optimization=OptimizationDefaults(),
        code_sha256="0" * 64,
        code_size=100,
        created_at=datetime(2026, 1, 1),
    )

    with pytest.raises(ValidationError):
        spec.num_states = 3


def test_system_spec_requires_code_and_source():
    import uuid
    from datetime import datetime

    from pydantic import ValidationError

    from app.domain.models import SystemSpec

    with pytest.raises(ValidationError):
        SystemSpec(
            system_id=uuid.uuid4(),
            name="Broken",
            num_states=1,
            num_inputs=1,
            simulation=SimulationDefaults(),
            optimization=OptimizationDefaults(),
            created_at=datetime(2026, 1, 1),
        )
