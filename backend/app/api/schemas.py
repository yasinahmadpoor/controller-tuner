from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.models import (
    Capability,
    ControllerType,
    Engine,
    JobStatus,
    OptimizationDefaults,
    RunType,
    SimulationDefaults,
)

ControllableMetric = Literal["mse", "settling_time", "overshoot", "control_effort"]


class ServiceStatus(BaseModel):
    ok: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str


NonNegativeWeights = dict[ControllableMetric, float]

ParamRanges = Annotated[
    dict[Literal["Kp", "Ki", "Kd"], tuple[float, float]],
    Field(min_length=1),
]

FixedTargets = dict[ControllableMetric, float]


class TargetRange(BaseModel):
    min: float
    max: float

    @model_validator(mode="after")
    def _check_ordered(self) -> TargetRange:
        if self.min >= self.max:
            raise ValueError(f"'min' must be less than 'max' (got {self.min}, {self.max})")
        return self


class CatalogEntryResponse(BaseModel):
    catalog_id: str
    name: str
    description: str | None = None
    objective: str | None = None
    num_states: int
    num_inputs: int
    target: float
    capabilities: list[Capability]
    sources: dict[str, str]


class CatalogResponse(BaseModel):
    items: list[CatalogEntryResponse]


class CreateSystemRequest(BaseModel):
    source: dict[str, Any]


class SystemResponse(BaseModel):
    system_id: UUID
    name: str
    description: str | None = None
    objective: str | None = None
    num_states: int
    num_inputs: int
    target: float
    capabilities: list[Capability]
    simulation: SimulationDefaults
    optimization: OptimizationDefaults
    created_at: datetime


class PaginatedResponse(BaseModel):
    items: list[SystemResponse]
    total: int
    limit: int
    offset: int


class SimulationOverrides(BaseModel):
    dt: float | None = None
    max_time: float | None = None
    target: float | None = None
    input_channel: int | None = None
    output_channel: int | None = None
    trim_values: list[float] | None = None
    min_control: float | None = None
    max_control: float | None = None
    initial_condition_range: tuple[float, float] | None = None
    randomness_level: float | None = None
    disturbance_level: float | None = None

    @model_validator(mode="after")
    def _validate_ranges(self) -> SimulationOverrides:
        if self.min_control is not None and self.max_control is not None:
            if self.min_control >= self.max_control:
                raise ValueError("'min_control' must be less than 'max_control'")
        return self


class SimulateRequest(BaseModel):
    controller_type: ControllerType
    params: dict[str, float]
    initial_state: list[float] | None = None
    seed: int | None = None
    overrides: SimulationOverrides | None = None


class SimulateResult(BaseModel):
    success: bool
    run_id: UUID
    engine: Engine
    controller_type: ControllerType
    params: dict[str, float]
    time_points: list[float]
    trajectory: list[float]
    control_signals: list[float]
    metrics: dict[str, Any]
    non_finite_metrics: list[str]


class GAConfig(BaseModel):
    population_size: int = Field(default=20, ge=5, le=200)
    generations: int = Field(default=30, ge=1, le=500)
    seed: int | None = None
    max_wall_clock: float = Field(default=120.0, gt=0)

    @model_validator(mode="after")
    def _validate_ranges(self) -> GAConfig:
        for name, (low, high) in {
            "population_size": (5, 200),
            "generations": (1, 500),
        }.items():
            value = getattr(self, name)
            if value < low:
                raise ValueError(f"'{name}' must be at least {low} (got {value})")
            if value > high:
                raise ValueError(f"'{name}' must be at most {high} (got {value})")
        return self


class OptimizeRequest(BaseModel):
    param_ranges: ParamRanges | None = None
    weights: NonNegativeWeights | None = None
    fixed_targets: FixedTargets | None = None
    ga_config: GAConfig | None = None
    async_: bool = Field(default=False, alias="async")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_ranges(self) -> OptimizeRequest:
        for name, (low, high) in (self.param_ranges or {}).items():
            if low >= high:
                raise ValueError(f"'{name}' range must be [low, high] with low < high")

        for metric, weight in (self.weights or {}).items():
            if weight < 0:
                raise ValueError(f"'{metric}' weight must be >= 0 (got {weight})")

        for metric, target in (self.fixed_targets or {}).items():
            if target <= 0:
                raise ValueError(f"'{metric}' target must be positive (got {target})")
        return self


class TargetHit(BaseModel):
    nfe: int | None = None
    time: float | None = None
    generation: int | None = None


class OptimizeResult(BaseModel):
    success: bool
    run_id: UUID
    engine: Engine
    controller_parameters: dict[str, float]
    achieved_metrics: dict[str, Any]
    ga_cost: float | None = None
    baseline_cost: float | None = None
    progress: dict[str, Any]
    stop_reason: Literal["normal", "score_100", "wall_clock"]
    num_evaluations: int
    target_hit: TargetHit
    warnings: list[str] = Field(default_factory=list)
    non_finite_metrics: list[str] = Field(default_factory=list)


class JobLink(BaseModel):
    self: str
    events: str
    run: str


class JobResponse(BaseModel):
    job_id: UUID
    run_id: UUID
    run_type: RunType
    status: JobStatus
    progress: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    links: JobLink | None = None


class RunSummary(BaseModel):
    run_id: UUID
    run_type: RunType
    engine: Engine
    status: str
    duration_ms: int | None = None
    created_at: datetime


class RunDetail(BaseModel):
    """Common persisted-run shape; concrete run types refine this in later phases."""

    model_config = ConfigDict(extra="allow")

    run_id: UUID
    run_type: RunType
    engine: Engine
    status: str
    duration_ms: int | None = None
    created_at: datetime
