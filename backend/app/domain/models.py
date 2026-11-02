from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ControllerType(StrEnum):
    P = "P"
    PI = "PI"
    PD = "PD"
    PID = "PID"
    FSF = "FSF"


class Engine(StrEnum):
    MANUAL = "manual_tuner"
    GA = "ga_tuner"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunType(StrEnum):
    SIMULATION = "simulation"
    OPTIMIZATION = "optimization"


class Capability(StrEnum):
    SIMULATE = "simulate"
    OPTIMIZE = "optimize"


class SystemSource(StrEnum):
    CATALOG_JSON = "catalog_json"
    CATALOG_PY = "catalog_py"
    UPLOADED_PY = "uploaded_py"
    INLINE_JSON = "inline_json"
    INLINE_CODE = "inline_code"


class ControlLimits(BaseModel):
    min: float
    max: float


class SimulationDefaults(BaseModel):
    dt: float = 0.01
    max_time: float = 10.0
    target: float = 0.0
    input_channel: int = 0
    output_channel: int = 0
    trim_values: list[float] = Field(default_factory=lambda: [0.0])
    trim_ics: list[float] | None = None
    min_control: float = -10.0
    max_control: float = 10.0
    initial_condition_range: tuple[float, float] = (-1.0, 1.0)
    randomness_level: float = 0.0
    disturbance_level: float = 0.0


class OptimizationDefaults(BaseModel):
    param_ranges: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {
            "Kp": (1.0, 50.0),
            "Ki": (0.01, 5.0),
            "Kd": (0.01, 10.0),
        }
    )
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "mse": 1.0,
            "settling_time": 0.5,
            "overshoot": 0.5,
            "control_effort": 0.1,
        }
    )
    fixed_targets: dict[str, float] = Field(
        default_factory=lambda: {
            "mse": 0.1,
            "settling_time": 3.0,
            "overshoot": 10.0,
            "control_effort": 0.1,
        }
    )
    ga: dict[str, float | int | None] = Field(
        default_factory=lambda: {
            "population_size": 20,
            "generations": 30,
            "seed": 42,
            "max_wall_clock": 120,
        }
    )


class SystemSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    system_id: UUID
    name: str
    description: str | None = None
    objective: str | None = None
    source_type: SystemSource
    source_ref: str | None = None

    num_states: int
    num_inputs: int
    capabilities: list[Capability] = Field(default_factory=lambda: [Capability.SIMULATE])

    simulation: SimulationDefaults
    optimization: OptimizationDefaults

    code_sha256: str
    code_size: int
    created_at: datetime
