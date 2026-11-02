# Unified Controller Tuning Platform — Architecture Plan

**Status:** Proposed — database-backed revision  
**Scope:** Unify `gaTunerPID` (GA auto-tuning) and `tunerPID` (manual simulation) behind one FastAPI backend with PostgreSQL + Redis, one React + Tailwind UI, Celery background workers, Docker Compose deployment, and automated tests.  
**Hard constraint:** The business logic in both repositories must not be modified. All engine code under `engines/gaTunerPID/src/` and `engines/tunerPID/src/` is treated as read-only.

---

## 1. Goals and non-goals

### Goals

1. Preserve both engines exactly as they are; add an integration layer around them.
2. Offer two complementary workflows from one product:
   - **Manual tuning:** load a system, choose a controller type (`P`, `PI`, `PD`, `PID`, `FSF`), run one simulation, inspect trajectories and metrics.
   - **Automatic tuning:** run the Genetic Algorithm to find `Kp`, `Ki`, `Kd` for fixed targets and weights, with generation progress and stop reasons.
3. Provide one coherent REST API and one React UI that work with both workflows.
4. Persist systems, uploaded code, simulation runs, optimization runs, jobs, and progress so results survive restarts and can be revisited.
5. Run long GA optimizations in Celery workers with Redis-backed progress and SSE streaming.
6. Start everything with `docker compose up --build`.
7. Cover the critical paths with unit, integration, and contract tests.

### Non-goals (for the first release)

- Modifying, refactoring, or re-implementing either engine.
- Adding new control-theory algorithms (e.g., GA for FSF gains).
- Multi-user accounts, authentication, or authorization.
- Multi-host job distribution and horizontal autoscaling (the Compose stack is single-host; the design leaves room for it).
- Direct comparison of numeric metrics across the two engines (their metric formulas differ by design).

---

## 2. Source repositories at a glance

### 2.1 `gaTunerPID` — automatic tuning engine

| Item | Detail |
|---|---|
| Core class | `src.ga_optimizer.GAOptimizer` |
| Simulator | `src.simulator.SystemSimulator` |
| Inputs | A `dynamics(t, x, u)` callable plus a complete `system_config` |
| Controller | PID only (`Kp`, `Ki`, `Kd`) |
| Output | Best gains, achieved metrics, generation progress, stop reason, NFE |
| Progress | Thread-local callback registry in `src.callbacks` |
| Case studies | JSON files embedding Python code + full metadata |
| Determinism | Deterministic when `seed` is set; simulator uses fixed `trim_ics` |

Key call signature (note the order):

```python
results = optimizer.optimize_pid(
    weights={...},
    param_ranges={"Kp": [...], "Ki": [...], "Kd": [...]},
    fixed_targets={...},
)
```

Relevant result fields: `success`, `controller_parameters`, `achieved_metrics`, `ga_cost`, `baseline_cost`, `warnings`, `progress`, `num_evaluations`, `stop_reason`, `target_hit_*`.

**Known drift in the reference Streamlit app:** `engines/gaTunerPID/app.py` calls `optimize_pid(targets, weights, param_ranges)`, which does not match the current engine signature, and later reads `results["cost"]`, which the engine does not return. The backend must follow the engine contract (`weights`, `param_ranges`, `fixed_targets`) and use `ga_cost`/`baseline_cost`. Contract tests must lock this down.

### 2.2 `tunerPID` — manual simulation engine

| Item | Detail |
|---|---|
| Core classes | `src.core.dynamics.DynamicalSystem`, `src.core.simulator.Simulator`, `src.core.metrics.MetricsCalculator` |
| Inputs | A `.py` file on disk exposing `dynamics(t, x, u)` |
| Controllers | `P`, `PI`, `PD`, `PID`, `FSF` |
| State detection | Automatic probing of `dynamics` (1–10 states) |
| Output | Full time series (`time_points`, `trajectory`, `control_signals`) plus rich metrics |
| Case studies | Plain `.py` files (no metadata) |
| Scenario controls | Random initial condition range, measurement noise, input disturbance, fixed target |
| Determinism | Deterministic when a fixed initial state and zero noise are supplied |

Key call signature:

```python
system = DynamicalSystem(path, num_inputs=1)
system.dt = 0.01
system.max_time = 5.0
system.target = 0.0
system.min_control = -10.0
system.max_control = 10.0
result = Simulator(system).evaluate("PID", params, fixed_initial_state=[1.0, 0.0])
```

### 2.3 Capability matrix

| Capability | `gaTunerPID` | `tunerPID` | Unified platform |
|---|---|---|---|
| Load embedded Python from JSON | Yes | No | Yes (canonical system loader) |
| Load `.py` upload | Partial (needs manual metadata) | Yes (auto-detects states) | Yes |
| Manual simulate `P/PI/PD/PID/FSF` | No | Yes | Manual workflow |
| GA optimize PID | Yes | No | Auto-tune workflow |
| Full trajectory output | Via `simulate_and_return_trajectory` | Yes | Manual workflow / optional replay |
| Rich progress callbacks | Yes | No | Job progress / SSE |
| Fixed-target success score | Yes | No | Auto-tune results |

### 2.4 Metric differences (important)

The engines report overlapping but not identical metrics and use different formulas:

| Concept | `gaTunerPID` key | `tunerPID` key | Notes |
|---|---|---|---|
| Mean squared error | `mse` | `mse`, `rmse` | Comparable name, different settling/overshoot context |
| Settling time | `settling_time` | `settling_time` | 2% band vs 5% band in the manual engine |
| Overshoot | `overshoot` | `overshoot` | Similar intent, different reference logic |
| Control effort | `control_effort` | `control_effort` | Same intent |
| Rise time | `rise_time` | `rise_time` | Different threshold logic |
| Steady-state error | `steady_state_error` | `ss_error` | Different windows |
| Stability flag | Not provided | `stable` | Manual only |
| Zero crossings | `control_zero_crossings` | `zero_crossings` | Different signal |

**Rule:** Never recompute or translate one engine's metrics into the other's. Return the engine-native metrics and label the engine in every response. The UI must not compare numbers across workflows as if they were equivalent.

---

## 3. Product concept

The unified platform is a **system workspace** with two tabs:

```
┌─────────────────────────────────────────────────────────────┐
│  Unified Controller Tuning Platform                         │
│                                                             │
│  System: Ball Beam   [2 states · 1 input · target 0.0]      │
│                                                             │
│  [ Manual Simulation ]   [ Auto-Tune (GA) ]                 │
│                                                             │
│  ┌───────────────────┐  ┌───────────────────────────────┐   │
│  │ Configuration     │  │ Results                       │   │
│  │ - controller type │  │ - charts                      │   │
│  │ - gains / ranges  │  │ - metrics                     │   │
│  │ - targets/weights │  │ - stability / stop reason     │   │
│  │ - GA settings     │  │ - export                      │   │
│  └───────────────────┘  └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

One **system** can be used by both workflows because the integration layer builds both engine-specific configurations from the same canonical `SystemSpec`.

---

## 4. High-level architecture

```
                    ┌─────────────────────────────────────┐
                    │        React + Tailwind SPA         │
                    │  Catalog · Manual · Auto · History  │
                    └───────────────┬─────────────────────┘
                                    │ HTTPS / JSON / SSE
                    ┌───────────────▼─────────────────────┐
                    │            FastAPI backend          │
                    │                                     │
                    │  API layer (routers, Pydantic)      │
                    │  Application services               │
                    │    - SystemService                  │
                    │    - SimulationService              │
                    │    - OptimizationService            │
                    │    - JobService                     │
                    │  Engine adapters                    │
                    │    - ManualEngineAdapter            │
                    │    - AutoTuneEngineAdapter          │
                    │  Repositories / Unit of Work        │
                    └───┬──────────┬──────────┬───────────┘
                        │          │          │
          ┌─────────────▼──┐ ┌─────▼─────┐ ┌──▼─────────────────┐
          │  PostgreSQL 16 │ │  Redis 7  │ │ Artifact storage   │
          │ systems/runs/  │ │ broker,   │ │ (code, optional    │
          │ jobs/artifacts │ │ progress, │ │  trajectories)     │
          └────────────────┘ │ locks,    │ └────────────────────┘
                             │ cache     │
                             └─────┬─────┘
                                   │ queue
                    ┌──────────────▼──────────────────────┐
                    │         Celery worker(s)            │
                    │  GA optimization · cleanup · SSE    │
                    │  events published to Redis Streams  │
                    └───────┬─────────────────┬───────────┘
                            │                 │
              ┌─────────────▼──────┐  ┌───────▼─────────────┐
              │  engines/tunerPID/src      │  │  engines/gaTunerPID/src     │
              │  (read-only)       │  │  (read-only)        │
              │  manual simulation │  │  GA optimization    │
              └────────────────────┘  └─────────────────────┘
```

The backend and worker are the only components that import engine code. The frontend never knows which engine produced a result beyond the `engine` field in responses. PostgreSQL is the system of record; Redis carries transient job/progress state; artifact storage holds uploaded code and optional large trajectories.

---

## 5. Proposed monorepo layout

The two source repositories remain untouched. The umbrella project adds new directories beside them.

```
task/
├── engines/gaTunerPID/                  # provided — read-only
│   ├── src/
│   ├── case_studies/json/
│   └── app.py
├── engines/tunerPID/                    # provided — read-only
│   ├── src/core/
│   ├── streamlit/
│   └── case_studies/
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory + lifespan
│   │   ├── api/
│   │   │   ├── deps.py          # DB session, pagination, auth deps later
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── routes/
│   │   │           ├── health.py
│   │   │           ├── catalog.py
│   │   │           ├── systems.py
│   │   │           ├── simulations.py
│   │   │           ├── optimizations.py
│   │   │           ├── runs.py          # persisted run history
│   │   │           ├── jobs.py
│   │   │           └── events.py        # SSE progress stream
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings
│   │   │   ├── logging.py
│   │   │   ├── exceptions.py    # domain exceptions + handlers
│   │   │   ├── security.py      # upload AST validation; auth later
│   │   │   ├── json_safe.py     # NaN/Inf/NumPy serialization
│   │   │   └── constants.py
│   │   ├── domain/              # engine-agnostic canonical models
│   │   │   ├── enums.py         # ControllerType, Engine, JobStatus
│   │   │   ├── entities.py      # SystemSpec, RunSpec, results
│   │   │   ├── engine_config.py # engine-specific config builders
│   │   │   └── errors.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   ├── unit_of_work.py  # transaction boundary for services
│   │   │   └── models/
│   │   │       ├── system.py
│   │   │       ├── artifact.py
│   │   │       ├── simulation_run.py
│   │   │       ├── optimization_run.py
│   │   │       ├── job.py
│   │   │       └── job_event.py # optional SSE replay
│   │   ├── schemas/
│   │   │   ├── common.py
│   │   │   ├── catalog.py
│   │   │   ├── system.py
│   │   │   ├── simulation.py
│   │   │   ├── optimization.py
│   │   │   ├── job.py
│   │   │   └── event.py
│   │   ├── repositories/
│   │   │   ├── base.py
│   │   │   ├── systems.py
│   │   │   ├── artifacts.py
│   │   │   ├── runs.py
│   │   │   └── jobs.py
│   │   ├── services/
│   │   │   ├── catalog_service.py
│   │   │   ├── system_service.py
│   │   │   ├── simulation_service.py
│   │   │   ├── optimization_service.py
│   │   │   ├── job_service.py
│   │   │   └── cleanup_service.py
│   │   ├── engines/             # critical read-only engine integration
│   │   │   ├── loader.py        # isolated imports of both engines
│   │   │   ├── manual_adapter.py
│   │   │   ├── auto_tune_adapter.py
│   │   │   ├── config_builder.py
│   │   │   └── normalize.py
│   │   ├── infrastructure/
│   │   │   ├── storage/         # code + large artifacts
│   │   │   │   ├── base.py
│   │   │   │   ├── local.py
│   │   │   │   └── s3.py        # optional MinIO/S3
│   │   │   ├── redis.py
│   │   │   ├── locks.py         # distributed locks
│   │   │   └── telemetry.py
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   ├── ga_tasks.py
│   │   │   ├── cleanup_tasks.py
│   │   │   └── progress.py      # publish progress to Redis Streams
│   │   ├── realtime/
│   │   │   ├── sse.py
│   │   │   └── progress_bus.py
│   │   ├── middleware/
│   │   │   ├── request_id.py
│   │   │   ├── logging.py
│   │   │   └── rate_limit.py
│   │   └── data/                # static catalog + defaults
│   │       ├── catalog/
│   │       │   ├── ball_beam.json
│   │       │   ├── dc_motor.json
│   │       │   └── inv_pendulum.json
│   │       └── defaults.py
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── factories.py
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── contract/
│   │   ├── e2e/
│   │   └── fixtures/
│   │       └── golden/
│   ├── scripts/
│   │   ├── seed_catalog.py
│   │   ├── verify_engines.py
│   │   ├── wait_for_dependencies.py
│   │   └── e2e_smoke.py
│   ├── docker/
│   │   ├── backend.Dockerfile
│   │   ├── worker.Dockerfile
│   │   ├── entrypoint-api.sh
│   │   ├── entrypoint-worker.sh
│   │   └── entrypoint-migrate.sh
│   ├── .env.example
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── .pre-commit-config.yaml
│   ├── README.md
│   └── Makefile
│
├── frontend/
│   ├── src/
│   │   ├── api/                 # typed client, query hooks
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   ├── catalog/
│   │   │   ├── system/
│   │   │   ├── manual/
│   │   │   ├── autotune/
│   │   │   ├── results/
│   │   │   ├── history/
│   │   │   └── ui/
│   │   ├── pages/
│   │   ├── charts/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/
│   ├── nginx.conf
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
│
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md           # this document
│   └── IMPLEMENTATION_PHASES.md
├── scripts/
│   ├── e2e_smoke.py              # API happy-path smoke test
│   └── verify_engines.py         # engine integrity checks
├── docker-compose.yml            # postgres + redis + migrate + backend + worker + frontend
├── docker-compose.dev.yml        # hot-reload developer stack
├── .env.example                  # shared compose environment template
└── README.md                     # short run instructions
```

---

## 6. Backend architecture

### 6.1 Layering

| Layer | Responsibility | Must not |
|---|---|---|
| API (`app/api`) | HTTP routing, request validation, status codes, response models | Contain engine calls, SQL queries, or business rules |
| Application services (`app/services`) | Orchestration: load system, build engine configs, persist runs, enqueue jobs | Import ORM models or engine modules directly |
| Repositories (`app/repositories`) | Persistence queries and transaction participation | Contain HTTP or engine logic |
| Engine adapters (`app/engines`) | Translate canonical models to engine calls and engine output to canonical results | Mutate engine source or duplicate physics/metrics |
| Workers (`app/workers`) | Celery tasks that execute GA runs and cleanup, publish progress | Serve HTTP |
| Infrastructure (`app/infrastructure`) | PostgreSQL sessions, Redis, locks, artifact storage, telemetry | Know about HTTP or domain rules |
| Domain (`app/domain`) | Canonical models, engine configs, enums, domain errors | Depend on FastAPI or SQLAlchemy |

### 6.2 Engine isolation — the critical integration problem

Both repositories expose a top-level Python package named `src`.

- `engines/gaTunerPID/src/*.py` uses absolute imports such as `from src.simulator import SystemSimulator`.
- `engines/tunerPID/src/core/*.py` uses relative imports such as `from .dynamics import DynamicalSystem`.

They cannot both be imported as `src` in the same process. The recommended solution is **no copying and no source edits**: load the manual engine under a distinct alias with `importlib`, and let the GA engine keep its native `src` name.

Validated loader sketch:

```python
# backend/app/engines/loader.py
import importlib.util
import sys
from pathlib import Path
from typing import Any

_loaded = False
_ga: dict[str, Any] = {}
_manual: dict[str, Any] = {}


def _load_alias(alias: str, src_dir: Path) -> None:
    """Load a package directory under an alternate name."""
    init = src_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        alias,
        str(init),
        submodule_search_locations=[str(src_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load engine package at {src_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)


def load_engines(ga_repo: Path, manual_repo: Path) -> None:
    global _loaded
    if _loaded:
        return

    # Manual engine: relative imports mean an alias is safe.
    _load_alias("manual_engine", manual_repo / "src")
    from manual_engine.core.dynamics import DynamicalSystem
    from manual_engine.core.simulator import Simulator
    from manual_engine.core.metrics import MetricsCalculator

    _manual.update(
        DynamicalSystem=DynamicalSystem,
        Simulator=Simulator,
        MetricsCalculator=MetricsCalculator,
    )

    # GA engine: its absolute imports require the name `src`.
    sys.path.insert(0, str(ga_repo))
    try:
        from src.simulator import SystemSimulator
        from src.ga_optimizer import GAOptimizer
        from src.callbacks import register_callback, unregister_callback

        _ga.update(
            SystemSimulator=SystemSimulator,
            GAOptimizer=GAOptimizer,
            register_callback=register_callback,
            unregister_callback=unregister_callback,
        )
    finally:
        sys.path.remove(str(ga_repo))

    _loaded = True


def manual() -> dict[str, Any]:
    return _manual


def ga() -> dict[str, Any]:
    return _ga
```

This approach was verified against both repositories: the manual engine imports as `manual_engine`, the GA engine imports as `src`, and a small GA run produces the expected result.

**Why not copy or rewrite imports?** Copying works, but it creates a second source of truth and risks accidental divergence. Runtime aliasing keeps the provided repositories as the only source of truth. If the deployment environment cannot support the alias approach, the fallback is a build-time vendoring script that copies `src` into namespaced directories and rewrites only import roots, with an integrity test that compares function bodies to the originals.

**Process-level alternative (not chosen for MVP):** run each engine in its own worker container. This maximizes isolation but adds operational overhead and duplicates engine dependencies and artifact access across workers.

### 6.3 Canonical domain model

All systems are normalized into one immutable description before either engine is called.

```python
# backend/app/domain/entities.py (illustrative)
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


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
    system_id: UUID
    name: str
    description: str | None = None
    objective: str | None = None
    source_type: Literal[
        "catalog_json", "catalog_py", "uploaded_py", "inline_json", "inline_code"
    ]
    source_ref: str | None = None

    num_states: int
    num_inputs: int
    capabilities: list[Literal["simulate", "optimize"]] = ["simulate"]

    simulation: SimulationDefaults
    optimization: OptimizationDefaults

    code_sha256: str
    code_size: int
    created_at: datetime
```

The generated code path and storage key are **not** part of the public model. The system row stores an `artifact_id`; the artifact row stores the storage key, SHA-256, size, and backend. The API never returns either value.

### 6.4 Loading and normalization

Canonical loading flow:

```
Input (catalog JSON / inline JSON / .py upload / inline code)
        │
        ▼
Security validation (extension, size, AST denylist)
        │
        ▼
Write code to artifact storage: <ARTIFACT_DIR>/<sha256>.py
        │
        ▼
Manual engine DynamicalSystem(path, num_inputs)
  - loads module
  - validates dynamics(t, x, u)
  - auto-detects num_states
        │
        ▼
Merge metadata:
  - JSON case study metadata wins when present
  - otherwise curated catalog metadata / user-provided defaults
        │
        ▼
Write code artifact (local volume or S3/MinIO) + artifact row
        │
        ▼
Build SystemSpec (immutable) + persist system row (PostgreSQL)
```

Mapping from `gaTunerPID` JSON case study to canonical fields:

| JSON field | Canonical field | Notes |
|---|---|---|
| `system_name` | `name` | |
| `system_description` | `description` | |
| `control_objective` | `objective` | |
| `python_code` | stored code | materialized to file |
| `num_states` | `num_states` | validate against auto-detection |
| `num_inputs` | `num_inputs` | |
| `input_channel` | `simulation.input_channel` | |
| `output_channel` | `simulation.output_channel` | |
| `target` | `simulation.target` | JSON wins over manual defaults |
| `min_ctrl` / `max_ctrl` | `simulation.min_control` / `max_control` | |
| `trim_values` | `simulation.trim_values` | scalar → one-element list |
| `trim_ics` | `simulation.trim_ics` | |
| `simulation_params.dt` | `simulation.dt` | |
| `simulation_params.max_time` | `simulation.max_time` | |
| `fixed_targets` | `optimization.fixed_targets` | |

Mapping from canonical `SystemSpec` to engine configurations:

**Auto-tune engine (`SystemSimulator` config):**

```python
{
    "dt": spec.simulation.dt,
    "max_time": spec.simulation.max_time,
    "target": spec.simulation.target,
    "num_states": spec.num_states,
    "num_inputs": spec.num_inputs,
    "input_channel": spec.simulation.input_channel,
    "output_channel": spec.simulation.output_channel,
    "min_ctrl": spec.simulation.min_control,
    "max_ctrl": spec.simulation.max_control,
    "trim_values": spec.simulation.trim_values,
    "trim_ics": spec.simulation.trim_ics or [0.0] * spec.num_states,
}
```

**Manual engine (`DynamicalSystem`):**

```python
system = DynamicalSystem(code_path, num_inputs=spec.num_inputs)
system.dt = spec.simulation.dt
system.max_time = spec.simulation.max_time
system.target = spec.simulation.target
system.input_channel = spec.simulation.input_channel
system.output_channel = spec.simulation.output_channel
system.min_control = spec.simulation.min_control
system.max_control = spec.simulation.max_control
system.trim_values = np.array(spec.simulation.trim_values)
system.initial_condition_range = spec.simulation.initial_condition_range
system.randomness_level = spec.simulation.randomness_level
system.disturbance_level = spec.simulation.disturbance_level
```

### 6.5 Engine adapters

#### Manual adapter

```python
class ManualEngineAdapter:
    def schema(self, spec: SystemSpec, controller_type: str) -> dict:
        system = self._build_system(spec)
        return system.get_param_schema(controller_type)

    def simulate(self, spec: SystemSpec, request: SimulateRequest) -> SimulateResult:
        system = self._build_system(spec, request.overrides)
        simulator = manual()["Simulator"](system)
        result = simulator.evaluate(
            request.controller_type,
            request.params,
            fixed_initial_state=request.initial_state,
        )
        return normalize_manual_result(result)
```

The system is built per request so concurrent requests cannot mutate shared engine state.

#### Auto-tune adapter

```python
class AutoTuneEngineAdapter:
    def optimize(self, spec: SystemSpec, request: OptimizeRequest) -> OptimizeResult:
        dynamics = load_dynamics_callable(spec)  # from manual loader
        simulator = ga()["SystemSimulator"](dynamics, build_ga_sim_config(spec))
        optimizer = ga()["GAOptimizer"](
            simulator,
            {
                "population_size": request.ga_config.population_size,
                "generations": request.ga_config.generations,
                "seed": request.ga_config.seed,
                "max_wall_clock": request.ga_config.max_wall_clock,
            },
        )
        raw = optimizer.optimize_pid(
            weights=request.weights,
            param_ranges=request.param_ranges,
            fixed_targets=request.fixed_targets,
        )
        return normalize_optimize_result(raw)
```

`load_dynamics_callable` uses the same `DynamicalSystem` instance created by the manual loader and exposes its loaded `dynamics` callable to the GA adapter. This avoids a second ad-hoc loader and ensures both engines see the same dynamics function.

### 6.6 Result normalization and JSON safety

Engine outputs contain values that the JSON serializer cannot represent:

- `numpy.float64`, `numpy.int64`, `numpy.ndarray`
- `NaN` in progress arrays (e.g., mean baseline cost)
- `Infinity` in manual metrics (`settling_time`, `rise_time`)

FastAPI/Starlette rejects `NaN` and `Infinity` in JSON responses. Every adapter must run results through a sanitizer:

```python
def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
```

Conventions:

- `null` in a numeric metric means "not finite" (e.g., the system never settled). The UI renders `∞` for `null` settling/rise time.
- `controller_parameters` are always plain Python `float`.
- Progress arrays preserve all engine fields, sanitized; no engine field is dropped.
- Each result includes `"engine": "manual_tuner" | "ga_tuner"`.

### 6.7 Persistence layer — PostgreSQL, Redis, and artifact storage

**Stack**

| Component | Choice | Purpose |
|---|---|---|
| PostgreSQL | 16 | System of record for systems, runs, jobs, artifact metadata |
| SQLAlchemy | 2.0 (sync API routes/workers, `psycopg`) | ORM and session management |
| Alembic | latest pinned | Schema migrations |
| Redis | 7 | Celery broker/result backend, progress Streams, locks, rate limits, cache |
| Artifact storage | local shared volume now; S3/MinIO adapter later | Uploaded `.py` code and optional large trajectory arrays |

**Database schema**

| Table | Purpose | Important columns |
|---|---|---|
| `systems` | Canonical system registry | `id UUID PK`, `name`, `description`, `objective`, `source_type`, `source_ref`, `num_states`, `num_inputs`, `capabilities JSONB`, `simulation_defaults JSONB`, `optimization_defaults JSONB`, `artifact_id FK`, `code_sha256`, `code_size`, `created_at`, `updated_at`, `expires_at` |
| `artifacts` | Code and optional large outputs | `id UUID PK`, `kind` (`code`, `trajectory`), `storage_backend`, `storage_key`, `sha256`, `size`, `content_type`, `created_at` |
| `simulation_runs` | Manual simulation history | `id UUID PK`, `system_id FK`, `controller_type`, `params JSONB`, `overrides JSONB`, `seed`, `engine`, `status`, `metrics JSONB`, `non_finite_metrics JSONB`, `trajectory_artifact_id FK NULL`, `duration_ms`, `created_at` |
| `optimization_runs` | GA run history | `id UUID PK`, `system_id FK`, `request JSONB`, `status`, `best_params JSONB`, `achieved_metrics JSONB`, `progress JSONB`, `stop_reason`, `num_evaluations`, `target_hit JSONB`, `warnings JSONB`, `error JSONB NULL`, `duration_ms`, `created_at`, `started_at`, `finished_at` |
| `jobs` | Async job state | `id UUID PK`, `run_id FK UNIQUE`, `run_type` (`simulation`, `optimization`), `status`, `progress JSONB`, `cancel_requested BOOL`, `worker_id`, `error JSONB NULL`, `created_at`, `started_at`, `finished_at`, `expires_at` |
| `job_events` | Optional SSE replay | `id BIGSERIAL PK`, `job_id FK`, `seq INT`, `event_type`, `payload JSONB`, `created_at` |

Design notes:

- Use JSONB for engine-specific configs and progress. The canonical domain model stays in Python; JSONB is an implementation detail.
- Do **not** store full trajectories in `simulation_runs`. Store metrics in Postgres and write the arrays as a compressed artifact (`.npz` or `.json.gz`) when trajectory history is enabled; otherwise regenerate on demand. This keeps the database small.
- `system_id`/`run_id` are UUIDs generated by the application. Add indexes on `(system_id, created_at DESC)`, `status`, and `expires_at`.
- Foreign keys use `ON DELETE CASCADE` so deleting a system removes its runs, jobs, and artifact references. Artifact blobs are removed by the cleanup service or storage lifecycle policy.
- `expires_at` supports TTL for uploaded systems and finished jobs. The cleanup task deletes expired rows and blobs. Retention is configurable (`SYSTEM_TTL_SECONDS`, `JOB_RETENTION_SECONDS`, `RUN_RETENTION_DAYS`).

**Repository and Unit-of-Work pattern**

```python
# backend/app/repositories/systems.py
class SystemRepository(BaseRepository[SystemModel]):
    def get(self, system_id: UUID) -> SystemModel | None: ...
    def list(self, *, limit: int, offset: int) -> list[SystemModel]: ...
    def add(self, system: SystemModel) -> None: ...
    def delete(self, system_id: UUID) -> bool: ...


# backend/app/db/unit_of_work.py
class UnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.systems = SystemRepository(self.session)
        self.artifacts = ArtifactRepository(self.session)
        self.runs = RunRepository(self.session)
        self.jobs = JobRepository(self.session)
        return self

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.rollback()
        self.session.close()
```

Services open a Unit of Work per request/task. Repositories never commit independently, so a service can atomically create an artifact record, a system row, and an audit run.

**Session strategy**

- Use **sync SQLAlchemy** for both API routes and Celery tasks to avoid maintaining two session/driver stacks. FastAPI routes that touch the DB are declared as `def` (run in the threadpool); the SSE route is `async def` and talks only to Redis via `redis.asyncio`.
- If the team strongly prefers an async API, add `db/session_async.py` with `asyncpg` and keep sync sessions for Celery. Do not mix both in one request path.
- One `Session` per request/task, created from the shared `sessionmaker`, closed in `finally`.

**Code artifact flow**

```
Upload / JSON code
      │
      ▼
AST validation + size check
      │
      ▼
Content-addressed storage: ${ARTIFACT_DIR}/<sha256>.py
      │
      ▼
artifacts row (kind=code, sha256, size, storage_key)
      │
      ▼
systems row (artifact_id, code_sha256, metadata)
```

- The worker and API must mount the same artifact volume (or use the same S3 bucket) so the worker can load the code.
- Never store user code in a path derived from the uploaded filename. Use `sha256` plus a generated extension.
- Deduplicate identical uploads by `sha256`; increment a reference count if the same artifact is reused, or rely on foreign keys and delete only when unreferenced.
- The public API never returns `storage_key` or source code.

**Redis responsibilities**

| Key / structure | Purpose | TTL |
|---|---|---|
| Celery broker/result | Task queue and result metadata | Celery-managed |
| `job:{job_id}:events` (Stream) | Generation progress for SSE and polling | `JOB_RETENTION_SECONDS` |
| `job:{job_id}:cancel` | Cooperative cancellation flag | `JOB_RETENTION_SECONDS` |
| `lock:system:{system_id}:ga` | Prevent duplicate concurrent optimizations for a system | Task duration + safety margin |
| `cache:system:{system_id}` | Optional metadata cache | 60–300 s |
| `ratelimit:{client}:{window}` | Request/job throttling | Window size |

**Hashing and IDs**

- Use UUIDv4 (or UUIDv7 if supported) for rows; generated in the application so tests can inject deterministic IDs.
- Use SHA-256 for code artifact deduplication.

**Migration workflow**

- `alembic upgrade head` runs in the one-shot `migrate` service before API/worker start, or in the API entrypoint before Uvicorn.
- The worker container waits for migrations via `scripts/wait_for_dependencies.py` (DB reachable + Alembic revision current).
- CI runs `alembic upgrade head` against a fresh Postgres container, then the full test suite.
- Never use `Base.metadata.create_all()` in production.

### 6.8 Background jobs — Celery, Redis, and SSE

GA runs can take seconds to minutes and are CPU-bound. The API supports two modes:

1. **Synchronous** (`async: false`, default for scripts): run the GA inline in a bounded API thread and persist the result. Suitable only for small runs.
2. **Asynchronous** (`async: true`, used by the React UI): enqueue a Celery task, return `202` with a `job_id`, then poll or stream progress.

**Celery topology**

```
FastAPI ── enqueue ──► Redis broker ──► Celery worker (prefork)
   │                                        │
   │ create job row                         │ run GA adapter
   │                                        │ publish progress to Redis Stream
   │◄──── poll/SSE ─── Redis Stream ────────┘
   │
   └── read final result from PostgreSQL
```

- `celery_app.py` configures the Redis broker/result, JSON serialization, `task_acks_late=True`, `worker_prefetch_multiplier=1`, and soft/hard time limits.
- Worker concurrency defaults to **1** (`MAX_CONCURRENT_GA_JOBS=1`) because PyGAD is CPU-heavy. Expose it as an environment variable for larger hosts.
- Use one queue (`ga`) for optimization. Cleanup and maintenance tasks use a separate `maintenance` queue so they are not blocked behind long GA runs.
- A Celery Beat schedule runs cleanup tasks (expired systems/jobs/artifacts) every few minutes.

**Task flow**

```python
# backend/app/workers/ga_tasks.py
@celery_app.task(bind=True, acks_late=True)
def run_optimization(self, job_id: str) -> None:
    with UnitOfWork(SessionLocal) as uow:
        job = uow.jobs.get(UUID(job_id))
        job.mark_running(worker_id=self.request.hostname)
        uow.commit()
        system = uow.systems.get(job.run.system_id)
        spec = system.to_domain()

        register_callback(
            lambda event: publish_progress(job_id, event)
        )
        try:
            result = AutoTuneEngineAdapter().optimize(spec, job.run.to_request())
            uow.runs.complete(job.run, result)
            job.mark_succeeded(result_summary=result)
            uow.commit()
            publish_terminal(job_id, "succeeded")
        except CancelledByUser:
            job.mark_cancelled()
            uow.commit()
            publish_terminal(job_id, "cancelled")
        except Exception as exc:
            uow.rollback()
            job.mark_failed(exc)
            uow.commit()
            publish_terminal(job_id, "failed")
        finally:
            unregister_callback()
```

- The callback runs inside the worker process/thread, so the engine's thread-local callback registry is correct.
- Progress events are published to the Redis Stream `job:{job_id}:events` with `XADD ... MAXLEN ~ 1000`. The database is **not** written on every generation; the final `progress` payload and terminal status are written once. This avoids write amplification.
- Redis Streams are read by the SSE endpoint with `XREAD BLOCK`; the endpoint also sends periodic keepalives. Polling reads the latest event from the stream and the job row.
- SSE: `GET /api/v1/jobs/{job_id}/events`. Clients that lose the stream fall back to `GET /api/v1/jobs/{job_id}`.
- Cancellation is **best effort**: the API sets `job.cancel_requested` in Postgres and `job:{id}:cancel` in Redis. The progress callback checks the flag and raises `StopIteration`, which the engine catches around `ga_instance.run()`. The worker marks the job `cancelled` regardless of the engine's reported `stop_reason`.
- If a worker dies, `task_acks_late` redelivers the task. The task handler resets the job to `running` and starts from the beginning (GA is not checkpointable without engine changes). Set a max retry count to avoid loops.
- Apply a distributed lock keyed by `system_id` so two users cannot run expensive optimizations for the same system concurrently. Release the lock in `finally`.
- Finished job results stay in Postgres per `JOB_RETENTION_SECONDS`; the cleanup task removes expired jobs, streams, and optional artifacts.

### 6.9 Security for uploaded Python

Executing user-provided Python in the backend process is remote code execution by design. The MVP must be explicit about this risk.

**MVP defenses (required):**

1. Accept only `.py`, maximum 256 KiB.
2. Parse with `ast`; reject the whole file if it contains:
   - imports: `os`, `sys`, `subprocess`, `socket`, `shutil`, `pathlib`, `importlib`, `ctypes`, `multiprocessing`, `threading`, `pickle`, `marshal`, `builtins`, `builtins` aliases.
   - calls/names: `eval`, `exec`, `compile`, `open`, `__import__`, `globals`, `locals`, `vars`, `getattr` with dynamic strings, `setattr`, `delattr`, `input`, `breakpoint`.
   - dunder attribute access such as `__class__`, `__bases__`, `__subclasses__`, `__globals__`.
   - `while True` / `for` loops at module import scope (best-effort static check).
3. Require a top-level `def dynamics(t, x, u)`.
4. Store files with generated names; never use the uploaded filename in a path.
5. Log only a hash and size of uploaded code, never the source.
6. Enforce request size limits and optimize caps (population, generations, max wall clock).

**Production hardening (recommended before exposing the service):**

- Run GA jobs in the dedicated Celery worker container with:
  - non-root user,
  - read-only root filesystem except the shared artifact scratch volume,
  - `no-new-privileges`,
  - CPU/memory limits,
  - no public network egress (only the internal Compose network),
  - no access to API secrets; give the worker only `DATABASE_URL`, `REDIS_URL`, and artifact paths.
- Do not mount the Docker socket, host home directory, or cloud credentials into the worker.
- Redact DB/Redis URLs and uploaded code from logs.
- Use secrets management or an `.env` file excluded from version control; never commit `POSTGRES_PASSWORD`.
- Optionally use a sandbox (gVisor, Firecracker, or a restricted subprocess with `seccomp`). Do not claim the AST denylist is a sandbox.

Document this risk in the root `README.md` as an explicit assumption.

---

## 7. API specification

Base URL: `/api/v1`. All request bodies are JSON unless noted. All responses are JSON. The API is versioned so the UI can evolve independently.

### 7.1 Health

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness: process is up |
| `GET` | `/ready` | Readiness: engines loaded, PostgreSQL reachable, Redis reachable, migrations current, artifact storage writable |

### 7.2 Catalog

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/catalog` | List built-in case studies discovered from both repositories |

Response:

```json
{
  "items": [
    {
      "catalog_id": "ball_beam",
      "name": "Ball Beam",
      "description": "Ball and beam system...",
      "objective": "Balance the ball...",
      "num_states": 2,
      "num_inputs": 1,
      "target": 0.0,
      "capabilities": ["simulate", "optimize"],
      "sources": {
        "json": "engines/gaTunerPID/case_studies/json/BallBeam.json",
        "python": "engines/tunerPID/case_studies/BallBeam.py"
      }
    }
  ]
}
```

Catalog entries are curated server-side metadata and do not expose code. If a source file is missing, the entry is omitted and a warning is logged.

### 7.3 Systems

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/systems` | Create a system from a catalog entry, JSON case study, or `.py` upload |
| `GET` | `/systems` | List persisted systems (`limit`, `offset`, optional `source_type`) |
| `GET` | `/systems/{system_id}` | Get canonical metadata |
| `DELETE` | `/systems/{system_id}` | Delete system, its runs/jobs, and unreferenced code artifacts |

#### `POST /systems`

**Mode A — catalog reference:**

```json
{
  "source": {
    "type": "catalog",
    "catalog_id": "ball_beam"
  }
}
```

**Mode B — full JSON case study (the shape of `engines/gaTunerPID/case_studies/json/*.json`):**

```json
{
  "source": {
    "type": "case_study_json",
    "case_study": { "...": "full JSON content" }
  }
}
```

**Mode C — inline Python code + metadata:**

```json
{
  "source": {
    "type": "python_code",
    "code": "import numpy as np\n\ndef dynamics(t, x, u): ...",
    "metadata": {
      "name": "My System",
      "num_inputs": 1,
      "target": 0.0,
      "min_control": -10.0,
      "max_control": 10.0,
      "input_channel": 0,
      "output_channel": 0,
      "trim_values": [0.0],
      "trim_ics": [1.0, 0.0],
      "dt": 0.01,
      "max_time": 10.0
    }
  }
}
```

**Mode D — multipart upload:**

`Content-Type: multipart/form-data`

- `file`: `.py` file (required)
- `metadata`: optional JSON string matching the metadata object above

Response (`201 Created`):

```json
{
  "system_id": "3f2c...",
  "name": "Ball Beam",
  "description": "Ball and beam system...",
  "num_states": 2,
  "num_inputs": 1,
  "target": 0.0,
  "capabilities": ["simulate", "optimize"],
  "simulation": {
    "dt": 0.01,
    "max_time": 20.0,
    "min_control": -0.5,
    "max_control": 0.5,
    "input_channel": 0,
    "output_channel": 0,
    "trim_values": [0.0],
    "trim_ics": [1.0, 0.0]
  },
  "optimization": {
    "param_ranges": { "Kp": [1.0, 50.0], "Ki": [0.01, 5.0], "Kd": [0.01, 10.0] },
    "weights": { "mse": 1.0, "settling_time": 0.5, "overshoot": 0.5, "control_effort": 0.1 },
    "fixed_targets": { "mse": 0.05, "settling_time": 1.0, "overshoot": 1.0, "control_effort": 0.1 },
    "ga": { "population_size": 20, "generations": 30, "seed": 42, "max_wall_clock": 120 }
  }
}
```

#### `GET /systems/{system_id}`

Returns the same shape as the create response. Never returns `python_code`, `storage_key`, or artifact paths.

#### `GET /systems`

Returns persisted systems, newest first:

```json
{
  "items": [ { "...": "SystemResponse" } ],
  "total": 12,
  "limit": 20,
  "offset": 0
}
```

### 7.4 Manual simulation

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/systems/{system_id}/schema?controller_type=PID` | Gain slider bounds for a controller type |
| `POST` | `/systems/{system_id}/simulate` | Run one closed-loop simulation with fixed gains |
| `POST` | `/systems/{system_id}/simulate/batch` | Optional: run N simulations with random ICs, return mean/std |

#### `GET /systems/{id}/schema?controller_type=PID`

Response:

```json
{
  "controller_type": "PID",
  "params": {
    "Kp": { "min": 0.1, "max": 60.0 },
    "Ki": { "min": 0.0, "max": 5.0 },
    "Kd": { "min": 0.0, "max": 20.0 }
  }
}
```

For `FSF`, the schema returns `K1` … `Kn` with `min` 0.01 and `max` 100.0, as defined by the engine.

#### `POST /systems/{id}/simulate`

Request:

```json
{
  "controller_type": "PID",
  "params": { "Kp": 15.0, "Ki": 0.5, "Kd": 2.0 },
  "initial_state": [1.0, 0.0],
  "seed": 42,
  "overrides": {
    "dt": 0.01,
    "max_time": 20.0,
    "target": 0.0,
    "min_control": -0.5,
    "max_control": 0.5,
    "input_channel": 0,
    "output_channel": 0,
    "trim_values": [0.0],
    "initial_condition_range": [-1.0, 1.0],
    "randomness_level": 0.0,
    "disturbance_level": 0.0
  }
}
```

- `initial_state` is optional. If omitted, the engine's random initial-condition behavior applies.
- `overrides` is optional. Omitted fields fall back to the system's defaults.
- `seed` seeds NumPy before the run when randomness is enabled; with a fixed initial state and zero noise it has no effect.

Response:

```json
{
  "success": true,
  "run_id": "c41d...",
  "engine": "manual_tuner",
  "controller_type": "PID",
  "params": { "Kp": 15.0, "Ki": 0.5, "Kd": 2.0 },
  "time_points": [0.0, 0.01, 0.02],
  "trajectory": [1.0, 0.99, 0.98],
  "control_signals": [10.0, 9.8, 9.5],
  "metrics": {
    "mse": 0.12,
    "rmse": 0.35,
    "settling_time": 1.23,
    "overshoot": 5.5,
    "stable": true,
    "ss_error": 0.001,
    "control_effort": 0.08,
    "rise_time": 0.4,
    "zero_crossings": 2
  },
  "non_finite_metrics": []
}
```

Metric values that are not finite are returned as `null` and listed in `non_finite_metrics`.

### 7.5 GA optimization

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/systems/{system_id}/optimize` | Run GA (sync) or enqueue a job (async) |
| `POST` | `/systems/{system_id}/trajectory` | Optional: replay best gains through the GA engine's trajectory method |

#### `POST /systems/{id}/optimize`

Request:

```json
{
  "param_ranges": {
    "Kp": [1.0, 50.0],
    "Ki": [0.01, 5.0],
    "Kd": [0.01, 10.0]
  },
  "weights": {
    "mse": 1.0,
    "settling_time": 0.5,
    "overshoot": 0.5,
    "control_effort": 0.1
  },
  "fixed_targets": {
    "mse": 0.05,
    "settling_time": 1.0,
    "overshoot": 1.0,
    "control_effort": 0.1
  },
  "ga_config": {
    "population_size": 20,
    "generations": 30,
    "seed": 42,
    "max_wall_clock": 120
  },
  "async": false
}
```

Validation rules:

- Each range must be `[low, high]` with `low < high`.
- `population_size` ≥ 5 and ≤ 200.
- `generations` ≥ 1 and ≤ 500.
- `weights` values ≥ 0.
- `fixed_targets` values > 0 (the engine divides by `max(target, 1e-6)`; positive targets are clearer).
- `max_wall_clock` > 0.
- `seed` optional; omit or `null` for stochastic runs.
- The system must have capability `optimize`; otherwise `409 Conflict` or `422`.

Synchronous response (`200`):

```json
{
  "success": true,
  "run_id": "b72e...",
  "engine": "ga_tuner",
  "controller_parameters": { "Kp": 12.3, "Ki": 0.4, "Kd": 3.1 },
  "achieved_metrics": {
    "mse": 0.03,
    "settling_time": 0.85,
    "overshoot": 0.7,
    "control_effort": 0.08,
    "rise_time": 0.3,
    "steady_state_error": 0.001,
    "control_zero_crossings": 4
  },
  "ga_cost": 0.21,
  "baseline_cost": -1.4,
  "progress": {
    "iteration": [1, 2, 3],
    "best_cost": [1.2, 0.9, 0.7],
    "mean_cost": [1.5, 1.1, 0.9],
    "best_params": [[1.0, 0.1, 0.2]],
    "Kp": [1.0],
    "Ki": [0.1],
    "Kd": [0.2],
    "success_score": [25],
    "best_score_so_far": [25],
    "cumulative_nfe": [40],
    "cumulative_wall_time": [0.8]
  },
  "stop_reason": "score_100",
  "num_evaluations": 412,
  "target_hit": { "nfe": 400, "time": 8.2, "generation": 20 },
  "warnings": [],
  "non_finite_metrics": []
}
```

Asynchronous response (`202 Accepted`):

```json
{
  "job_id": "8a1b...",
  "run_id": "b72e...",
  "status": "queued",
  "links": {
    "self": "/api/v1/jobs/8a1b...",
    "events": "/api/v1/jobs/8a1b.../events",
    "run": "/api/v1/optimizations/b72e..."
  }
}
```

#### Jobs

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/jobs/{job_id}` | Current status, last progress event, result or error |
| `GET` | `/jobs/{job_id}/events` | SSE stream of progress and terminal events |
| `POST` | `/jobs/{job_id}/cancel` | Best-effort cancellation |

Job status values: `queued`, `running`, `succeeded`, `failed`, `cancelled`.

Poll response:

```json
{
  "job_id": "8a1b...",
  "run_id": "b72e...",
  "system_id": "3f2c...",
  "status": "running",
  "progress": {
    "generation": 12,
    "cumulative_nfe": 480,
    "cumulative_wall_time": 9.4,
    "best_score_so_far": 75,
    "success_score": 75,
    "Kp": 14.2,
    "Ki": 0.31,
    "Kd": 5.6
  },
  "result": null,
  "error": null,
  "created_at": "2026-01-01T10:00:00Z",
  "started_at": "2026-01-01T10:00:00Z",
  "finished_at": null
}
```

SSE events:

```
event: progress
data: {"generation":12,"cumulative_nfe":480,...}

event: done
data: {"status":"succeeded","job_id":"8a1b..."}
```

If the client loses the stream, it falls back to polling.

### 7.6 Run history

Because systems and runs are persisted, the UI can list and reopen past results.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/systems/{system_id}/simulations` | Paginated simulation history for a system |
| `GET` | `/systems/{system_id}/optimizations` | Paginated optimization history for a system |
| `GET` | `/simulations/{run_id}` | One persisted manual run (metadata + metrics) |
| `GET` | `/optimizations/{run_id}` | One persisted GA run (request, result, progress) |
| `DELETE` | `/simulations/{run_id}` | Delete a simulation run |
| `DELETE` | `/optimizations/{run_id}` | Delete an optimization run |

List response shape:

```json
{
  "items": [
    {
      "run_id": "c41d...",
      "system_id": "3f2c...",
      "engine": "manual_tuner",
      "controller_type": "PID",
      "status": "succeeded",
      "created_at": "2026-01-01T10:00:00Z",
      "summary": { "mse": 0.12, "settling_time": 1.23, "stable": true }
    }
  ],
  "total": 8,
  "limit": 20,
  "offset": 0
}
```

Optimization detail includes the original request, best parameters, achieved metrics, full progress, stop reason, and `target_hit`. Large trajectory arrays are not returned by default; request `?include_artifacts=true` on a simulation run to receive them when the artifact exists. Otherwise, the client can re-run the simulation with the stored parameters.

### 7.7 Optional trajectory replay

`POST /systems/{id}/trajectory`

Request:

```json
{
  "params": { "Kp": 12.3, "Ki": 0.4, "Kd": 3.1 },
  "runs": 10,
  "seed": 42
}
```

Response: `runs`, `time_points`, `trajectory_mean`, `trajectory_std`, `control_mean`, `control_std`, `successful_runs`, `engine: "ga_tuner"`.

This uses `SystemSimulator.simulate_and_return_trajectory` so the replay is consistent with the GA engine. It returns trajectories only, not metrics, to avoid implying metric parity with the manual engine.

### 7.8 Error model

All errors use one envelope:

```json
{
  "error": {
    "code": "system_not_found",
    "message": "System 3f2c... was not found or has expired.",
    "context": {}
  }
}
```

| Status | Code examples | When |
|---|---|---|
| `400` | `invalid_python`, `unsafe_import`, `invalid_metadata` | Upload/content validation fails |
| `404` | `system_not_found`, `run_not_found`, `job_not_found`, `catalog_entry_not_found` | Unknown, deleted, or expired ID |
| `409` | `capability_not_supported`, `job_not_cancellable`, `optimization_in_progress` | Valid request, wrong resource state or duplicate GA lock |
| `413` | `payload_too_large` | Upload exceeds size limit |
| `415` | `unsupported_media_type` | Not `.py` / wrong content type |
| `422` | `validation_error` | Pydantic validation failure |
| `429` | `job_queue_full`, `rate_limited` | Too many queued jobs or requests |
| `500` | `engine_error`, `storage_error` | Unexpected engine or artifact storage failure |
| `503` | `service_not_ready` | Engines failed to load, DB/Redis unreachable, migrations pending, or artifact storage unavailable |

### 7.9 CORS

- Development: allow `http://localhost:5173` and `http://localhost:3000` via `CORS_ORIGINS`.
- Production: the frontend is served by nginx and proxies `/api` to the backend, so requests are same-origin and CORS is not needed. Keep `CORS_ORIGINS` configurable and empty by default in production.

---

## 8. Frontend architecture

### 8.1 Stack

- **React 18 + TypeScript + Vite**
- **Tailwind CSS** for styling
- **React Router** for navigation
- **TanStack Query** for server-state caching, retries, and loading/error states
- **React Hook Form + Zod** for complex optimization forms
- **Recharts** for time-series and progress charts (lighter than Plotly and easy to style with Tailwind)
- **Vitest + React Testing Library + MSW** for component and hook tests
- **Playwright** (optional) for one end-to-end happy path

### 8.2 Routes

```
/                          → redirect to /systems
/systems                   → catalog + upload
/systems/:systemId         → workspace (defaults to Manual tab)
/systems/:systemId/manual  → manual simulation tab
/systems/:systemId/auto    → auto-tune tab
/systems/:systemId/history → persisted run history
/runs/:runId               → persisted run detail (simulation or optimization)
/jobs/:jobId               → job detail (optional; can be inline)
```

The selected system and tab are reflected in the URL so results are shareable and refresh-safe.

### 8.3 Component tree

```
App
├── AppShell
│   ├── Header (product name, backend status)
│   └── ToastHost
├── CatalogPage
│   ├── CaseStudyGrid
│   │   └── CaseStudyCard (name, states, target, capabilities)
│   └── UploadSystemDialog
│       ├── FileDropzone (.py only)
│       └── UploadMetadataForm
├── WorkspacePage
│   ├── SystemSummaryCard
│   ├── WorkflowTabs
│   ├── ManualTuningTab
│   │   ├── ControllerTypeSelect
│   │   ├── GainSliderGroup (schema-driven)
│   │   ├── SimulationSettingsForm (collapsible advanced)
│   │   ├── InitialStateInput
│   │   └── RunSimulationButton
│   ├── AutoTuneTab
│   │   ├── ParamRangeEditor (Kp/Ki/Kd)
│   │   ├── TargetsWeightsEditor
│   │   ├── GAConfigForm
│   │   ├── ResetToDefaultsButton
│   │   └── OptimizeButton
│   ├── HistoryTab
│   │   ├── RunHistoryList (simulations + optimizations)
│   │   ├── RunFilters (type, status, date)
│   │   └── RunDetailDrawer / RunDetailPage
│   ├── ManualResults
│   │   ├── TrajectoryChart (target reference line)
│   │   ├── ControlChart
│   │   ├── MetricsPanel
│   │   └── StabilityBadge
│   └── AutoTuneResults
│       ├── BestGainsCard
│       ├── StopReasonBadge
│       ├── ProgressCharts (cost, gains, score)
│       ├── MetricsVsTargetsTable
│       ├── JobProgressPanel (async mode)
│       ├── TrajectoryReplayChart (optional)
│       └── ExportMenu (JSON / CSV)
└── common
    ├── ErrorBanner
    ├── LoadingSpinner
    ├── EmptyState
    └── NumberField / RangeField
```

### 8.4 State management

- **Server state:** TanStack Query hooks:
  - `useCatalog()`
  - `useSystem(systemId)`
  - `useSchema(systemId, controllerType)`
  - `useSimulate()` mutation
  - `useOptimize()` mutation
  - `useSystemRuns(systemId, type)` history list with pagination
  - `useRun(runId)` persisted run detail
  - `useJob(jobId)` with polling fallback
  - `useJobEvents(jobId)` SSE hook
  - `useDeleteRun(runId)` cache invalidation
- **Form state:** React Hook Form; Zod schemas mirror the backend Pydantic constraints.
- **Local UI state:** selected tab, advanced settings visibility, chart toggles.
- **No global client-state library** is required for the MVP.

### 8.5 API client

```ts
// frontend/src/api/client.ts
const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.error?.code, body?.error?.message);
  }
  return response.json() as Promise<T>;
}
```

- `VITE_API_URL` is the only environment-specific setting. Development: `http://localhost:8000/api/v1`. Production: `/api/v1` (same origin via nginx).
- Types in `src/types/` mirror the OpenAPI schema; optionally generate them with `openapi-typescript` in CI.

### 8.6 UX requirements

- Disable submit buttons while a request is in flight; show a spinner and a status message.
- Show inline validation errors before submission.
- Show backend error messages in a dismissible banner.
- Show a stability badge for manual results (`Stable` / `Unstable`).
- Show achieved metrics next to targets with a visual hit/miss indicator in auto-tune.
- Show the stop reason (`normal`, `score_100`, `wall_clock`) as a badge with an explanation.
- Provide "Reset to case-study defaults" on the auto-tune form.
- Provide export of the best gains as JSON and CSV.
- Render `null` metrics as `∞` where appropriate and add a tooltip explaining non-finite values.
- Keep advanced simulation settings collapsed by default so the happy path stays simple.
- Show a **History** tab listing persisted simulations and optimizations with status, timestamp, and key metrics; allow reopening and deleting a run.
- Persist the latest result view from the run record so a page refresh restores results.
- Show a retention note when a run is close to expiry or has been deleted.
- Responsive layout: configuration and results stack vertically on small screens.

### 8.7 Chart plan

| Chart | Data | Library |
|---|---|---|
| System response | `time_points` vs `trajectory`, target reference line | Recharts `LineChart` + `ReferenceLine` |
| Control input | `time_points` vs `control_signals` | Recharts `LineChart` |
| GA cost history | `progress.iteration` vs `best_cost`, `mean_cost` | Recharts `LineChart` |
| GA gains history | `progress.iteration` vs `Kp`, `Ki`, `Kd` | Recharts `LineChart` (three lines) |
| Success score | `progress.iteration` vs `success_score`, `best_score_so_far` | Recharts `LineChart` |
| Trajectory replay (optional) | time vs mean and ±1 std | Recharts `AreaChart` + `Line` |

Charts use the same color tokens for output, control, target, and gains across the app.

---

## 9. Docker and deployment architecture

### 9.1 Services

```yaml
# docker-compose.yml (shape)
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: controller_tuner
      POSTGRES_USER: tuner
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tuner -d controller_tuner"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  migrate:
    build:
      context: .
      dockerfile: backend/docker/backend.Dockerfile
    command: ["/app/docker/entrypoint-migrate.sh"]
    environment:
      DATABASE_URL: postgresql+psycopg://tuner:${POSTGRES_PASSWORD}@postgres:5432/controller_tuner
    depends_on:
      postgres:
        condition: service_healthy

  backend:
    build:
      context: .
      dockerfile: backend/docker/backend.Dockerfile
    environment:
      APP_ENV: production
      DATABASE_URL: postgresql+psycopg://tuner:${POSTGRES_PASSWORD}@postgres:5432/controller_tuner
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      GA_ENGINE_REPO: /app/engines/gaTunerPID
      MANUAL_ENGINE_REPO: /app/engines/tunerPID
      ARTIFACT_DIR: /data/artifacts
      ARTIFACT_BACKEND: local
      CORS_ORIGINS: ""
      MAX_UPLOAD_BYTES: "262144"
      SYSTEM_TTL_SECONDS: "86400"
      JOB_RETENTION_SECONDS: "3600"
      MAX_CONCURRENT_GA_JOBS: "1"
    volumes:
      - artifacts_data:/data/artifacts
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/api/v1/health"]
      interval: 10s
      timeout: 3s
      retries: 5
    ports:
      - "8000:8000"

  worker:
    build:
      context: .
      dockerfile: backend/docker/worker.Dockerfile
    command:
      - celery
      - -A
      - app.workers.celery_app
      - worker
      - -Q
      - ga,maintenance
      - --concurrency=${MAX_CONCURRENT_GA_JOBS:-1}
      - --loglevel=INFO
    environment:
      DATABASE_URL: postgresql+psycopg://tuner:${POSTGRES_PASSWORD}@postgres:5432/controller_tuner
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      GA_ENGINE_REPO: /app/engines/gaTunerPID
      MANUAL_ENGINE_REPO: /app/engines/tunerPID
      ARTIFACT_DIR: /data/artifacts
      ARTIFACT_BACKEND: local
      MAX_CONCURRENT_GA_JOBS: "1"
    volumes:
      - artifacts_data:/data/artifacts
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully

  beat:
    build:
      context: .
      dockerfile: backend/docker/worker.Dockerfile
    command: ["celery", "-A", "app.workers.celery_app", "beat", "--loglevel=INFO"]
    environment:
      DATABASE_URL: postgresql+psycopg://tuner:${POSTGRES_PASSWORD}@postgres:5432/controller_tuner
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      ARTIFACT_DIR: /data/artifacts
      ARTIFACT_BACKEND: local
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_URL: /api/v1
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "3000:80"

volumes:
  postgres_data:
  redis_data:
  artifacts_data:
```

`migrate` is a one-shot service: it runs `alembic upgrade head` and exits. `backend`, `worker`, and `beat` wait for it via `service_completed_successfully`.

### 9.2 Backend image

- Base: `python:3.12-slim` (both engines require Python 3.10+).
- Install pinned requirements from `backend/requirements.txt`.
- Copy the umbrella backend plus the two read-only engine repositories into `/app/engines/`.
- Set `PYTHONPATH=/app` and engine paths via environment.
- Run as a non-root user with a writable artifact volume.
- Run `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}`. The API can scale beyond one worker because state lives in PostgreSQL/Redis; keep the default at 1 until load-tested.
- API and worker share the same code image but use different entrypoints.

Example Dockerfile outline:

```dockerfile
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/scripts ./scripts
COPY backend/docker ./docker
COPY engines/gaTunerPID ./engines/gaTunerPID
COPY engines/tunerPID ./engines/tunerPID

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/artifacts && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### 9.3 Worker image

- Same base image and dependencies as the backend.
- Different entrypoint: Celery worker instead of Uvicorn.
- Non-root user, no published ports, no access to public network except the Compose network.
- Shared artifact volume with the backend.
- `--concurrency` driven by `MAX_CONCURRENT_GA_JOBS` (default 1).
- Set Celery soft/hard time limits from `GA_TASK_SOFT_TIME_LIMIT` / `GA_TASK_TIME_LIMIT`.
- Prefer `worker` + `beat` as separate services; do not run Beat inside the worker for production.

### 9.4 Frontend image

- Multi-stage: `node:20-alpine` build, `nginx:alpine` runtime.
- Build with `VITE_API_URL=/api/v1`.
- Nginx serves the SPA and proxies `/api/` to `http://backend:8000/api/`.
- No hard-coded container IPs; service DNS names are used.

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
        proxy_buffering off;  # required for SSE
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

`proxy_buffering off` and a longer `proxy_read_timeout` are required for SSE progress streaming.

### 9.5 Development stack

`docker-compose.dev.yml`:

- Postgres and Redis services with exposed ports (`5432`, `6379`) for local tools.
- `migrate` runs `alembic upgrade head` on startup; for rapid iteration, run `alembic revision --autogenerate` locally.
- Backend: bind-mount `backend/app`, `engines/gaTunerPID`, and `engines/tunerPID`; run `uvicorn --reload`.
- Worker: bind-mount the same paths; run Celery with `--pool=solo` or concurrency 1 for easier debugging.
- Frontend: bind-mount `frontend/`; run `npm run dev -- --host 0.0.0.0`; expose `5173`.
- `VITE_API_URL=http://localhost:8000/api/v1`.
- CORS enabled for `http://localhost:5173`.

Production and development share the same engine paths, env variable names, and migration flow.

### 9.6 Operational notes

- API and worker are stateless except for the shared artifact volume; PostgreSQL and Redis hold the durable/transient state.
- The `postgres_data` volume is the system of record. Back it up according to your retention policy.
- The `artifacts_data` volume holds uploaded code and optional trajectory artifacts. It must be readable and writable by both `backend` and `worker`.
- Redis persistence (`appendonly yes`) protects progress streams and Celery state across restarts, but Redis is not the system of record.
- Set container CPU/memory limits when multiple users share the deployment; GA is CPU-heavy. Keep worker concurrency low unless the host has spare cores.
- Health checks must not import engines or run migrations on every call; check cached readiness flags set at startup.
- Run migrations as a one-shot service and fail fast if the DB is unreachable; never start the API against an outdated schema.
- Configure a Postgres backup/restore procedure and a Redis eviction policy that does not evict active job streams (`maxmemory-policy noeviction` or a dedicated Redis instance for jobs).

---

## 10. Testing strategy

### 10.1 Test pyramid

| Level | Scope | Tools | Examples |
|---|---|---|---|
| Contract | Engine behavior untouched | pytest, NumPy assertions | Seeded BallBeam outputs match golden snapshots |
| Unit | Adapters, normalizers, validators, repositories | pytest | JSON serialization, metric `null` handling, AST denylist, repository queries |
| Integration | FastAPI + PostgreSQL + Redis + real engines (tiny configs) | pytest + `TestClient`/`httpx`, testcontainers | Create system → simulate → optimize with pop 5/gens 2; history survives restart |
| Migration | Alembic schema and upgrade path | pytest + testcontainers | `alembic upgrade head` from empty DB; downgrade/upgrade smoke |
| Frontend unit | Components and hooks | Vitest + RTL + MSW | GainSchema renders sliders, error banner on 500, loading states |
| E2E | Full happy path | Playwright (optional) or API smoke script | Load BallBeam → simulate → optimize → export → reopen from history |
| Docker smoke | Build and run full stack | shell/CI | `docker compose up --build -d`, wait for health, run `scripts/e2e_smoke.py` |

### 10.2 Engine contract tests

These are mandatory because the engines are read-only and we rely on their behavior.

```python
# backend/tests/contract/test_manual_engine_contract.py
def test_ballbeam_pid_is_deterministic(engines, ballbeam_py):
    system = engines.manual.DynamicalSystem(ballbeam_py, num_inputs=1)
    system.dt = 0.01
    system.max_time = 1.0
    system.target = 0.0
    system.min_control = -0.5
    system.max_control = 0.5
    result = engines.manual.Simulator(system).evaluate(
        "PID", {"Kp": 15.0, "Ki": 0.5, "Kd": 2.0},
        fixed_initial_state=[1.0, 0.0],
    )
    assert set(result) == {"success", "time_points", "trajectory", "control_signals", "metrics"}
    assert result["metrics"]["mse"] == pytest.approx(0.42509222491165505, rel=1e-9)
```

```python
# backend/tests/contract/test_ga_engine_contract.py
def test_ballbeam_ga_smoke(engines, ballbeam_json):
    config = build_ga_sim_config(ballbeam_json, max_time=1.0)
    simulator = engines.ga.SystemSimulator(load_dynamics(ballbeam_json), config)
    optimizer = engines.ga.GAOptimizer(simulator, {"population_size": 5, "generations": 2, "seed": 42})
    result = optimizer.optimize_pid(
        weights={"mse": 1.0, "settling_time": 0.5, "overshoot": 0.5, "control_effort": 0.1},
        param_ranges={"Kp": [1.0, 50.0], "Ki": [0.01, 5.0], "Kd": [0.01, 10.0]},
        fixed_targets={"mse": 0.05, "settling_time": 1.0, "overshoot": 1.0, "control_effort": 0.1},
    )
    assert "controller_parameters" in result
    assert result["progress"]["iteration"] == [1, 2]
    assert result["stop_reason"] in {"normal", "score_100", "wall_clock"}
```

Golden snapshots should be stored as JSON with tolerances (`pytest.approx`, `numpy.testing.assert_allclose`). Pin `numpy` and `pygad` versions in `requirements.txt` so snapshots remain stable.

### 10.3 API integration tests

- `POST /systems` with catalog, JSON case study, inline code, multipart `.py`.
- `GET /systems/{id}` returns no `python_code`, storage key, or artifact path.
- Unknown system → `404` with the error envelope.
- Invalid controller type → `422`.
- Unsafe import (`import os`) → `400`.
- Manual simulate → series lengths match, metrics keys present, non-finite values are `null`; a `simulation_runs` row is created.
- GA optimize with `population_size=5, generations=2, seed=42` → deterministic gains, progress length 2, stop reason valid; an `optimization_runs` row is created.
- Async optimize → `202`, poll until `succeeded`, result shape matches sync, `jobs` row reaches `succeeded`.
- Cancel a running job → status `cancelled` (best effort; use a large enough run to cancel).
- Worker restart / task redelivery → job does not remain `running` forever.
- Delete a system → runs/jobs are cascade-deleted; subsequent calls return `404`.
- Expired systems/jobs are removed by the cleanup task (use an injectable clock or short TTL).
- History endpoints return persisted runs and support pagination.
- Artifact storage round-trip: uploaded code can be loaded by the worker after an API restart.
- CORS preflight from the dev origin succeeds when configured.

### 10.4 Frontend tests

- Catalog renders cards from mocked `/catalog`.
- Upload dialog rejects non-`.py` files.
- Gain sliders are generated from the schema endpoint.
- Manual simulate shows spinner, disables the button, then renders charts and metrics.
- Auto-tune shows validation errors for an inverted range.
- Optimize result renders best gains, metrics vs targets, stop reason, and progress charts.
- API error renders the error banner and re-enables the form.
- SSE hook falls back to polling when `EventSource` fails (mock).

### 10.5 CI pipeline

```yaml
jobs:
  backend:
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: test, POSTGRES_USER: test, POSTGRES_PASSWORD: test }
      redis:
        image: redis:7-alpine
    steps:
      - ruff check backend
      - mypy backend/app (optional)
      - alembic -c backend/alembic.ini upgrade head
      - pytest backend/tests --cov=backend/app --cov-fail-under=80
  frontend:
    steps:
      - npm ci
      - npm run lint
      - npm run test -- --run
      - npm run build
  docker:
    steps:
      - docker compose build
      - docker compose up -d
      - wait for /api/v1/ready
      - python scripts/e2e_smoke.py
      - docker compose down -v
```

The coverage threshold applies to the integration code (`backend/app`), not to the read-only engines. Engine behavior is protected by contract tests.

Integration tests run against real PostgreSQL and Redis containers (or `pytest-postgresql` + `fakeredis` for fast unit-level coverage). Each test transaction is rolled back or the schema is truncated between tests. Migrations are applied once per session; a dedicated migration test applies every revision from an empty database. Artifact storage is tested with a temporary local directory and, optionally, a MinIO container.

---

## 11. Observability and performance

### Logging

- Structured JSON logs (or key-value logs in development).
- Include `request_id`, `system_id`, `job_id`, `engine`, `duration_ms`, `num_evaluations`, `stop_reason`.
- Never log uploaded source code or full trajectory arrays.
- Log engine load failures at startup as errors; fail readiness.

### Metrics (optional)

- HTTP request count and latency by route and status.
- Active jobs, queued jobs, job duration, retries, GA stop reasons.
- Celery queue depth and worker concurrency utilization.
- PostgreSQL connection pool usage, slow queries, failed transactions.
- Redis memory usage, stream length, evictions, lock contention.
- Artifact storage bytes written/read and cleanup deletions.
- Uploaded code validation rejections.
- Persisted system/run counts and expired-record sweep count.

### Performance guardrails

- Cap upload size at 256 KiB.
- Cap GA population at 200 and generations at 500.
- Cap concurrent GA jobs at 1 by default; enforce the queue limit in Redis and return `429` when full.
- Set a default `max_wall_clock` of 120 seconds per optimization and Celery soft/hard time limits.
- Keep Redis progress streams bounded with `MAXLEN ~ 1000`; do not write progress to Postgres per generation.
- Run cleanup on a Celery Beat schedule for expired systems, jobs, streams, and artifacts.
- Avoid re-loading engine modules per request; cache references at startup in each API/worker process.
- Instantiate engine objects per request/job to avoid shared mutable state.
- Use connection pooling with sane limits (`pool_size`, `max_overflow`) and one session per request/task.
- Add pagination to list/history endpoints; never return unbounded result sets.

---

## 12. Key design decisions (ADR summary)

| ID | Decision | Rationale | Consequence |
|---|---|---|---|
| ADR-001 | Add an adapter/anti-corruption layer; do not modify engines | Hard constraint; preserves upstream behavior | All new code lives in `backend/` and `frontend/` |
| ADR-002 | Isolate engine imports at runtime (`src` + `manual_engine` alias) | Both packages are named `src`; copying creates drift | One process can host both engines; loader is a critical module with contract tests |
| ADR-003 | One canonical `SystemSpec`, engine-specific configs derived from it | Avoid parallel metadata models | JSON case-study metadata is authoritative; defaults fill gaps |
| ADR-004 | Return engine-native metrics with an `engine` field; never recompute across engines | Formulas differ | UI labels the workflow and avoids cross-engine comparisons |
| ADR-005 | PostgreSQL as system of record; Redis for queue/progress/locks/cache | Durable history and multi-process state for API and Celery workers | Requires migrations, backups, and connection-pool tuning; Redis is not the source of truth |
| ADR-006 | Celery + Redis workers for async GA; sync mode retained for scripts | GA is CPU-bound and long-running; the UI needs progress | Adds worker/beat services, retry semantics, and queue monitoring |
| ADR-007 | Recharts for charts | Lighter bundle and easy Tailwind styling | Plotly-specific features not available; simple charts are enough |
| ADR-008 | Nginx same-origin proxy in production | Avoids CORS and hard-coded container URLs | `VITE_API_URL=/api/v1`; SSE proxy buffering disabled |
| ADR-009 | AST denylist for uploads; isolated worker container | Keeps scope sane while naming the risk | Not a sandbox; do not run untrusted code on a host with secrets |
| ADR-010 | Pin engine dependencies and golden-test seeded runs | PyGAD/numpy can change behavior across versions | Upgrades require updating snapshots intentionally |
| ADR-011 | Sync SQLAlchemy for API and Celery; `redis.asyncio` only for SSE | Avoids two ORM driver/session stacks while keeping SSE non-blocking | DB-touching routes are declared `def` and run in the threadpool |
| ADR-012 | Artifact storage abstraction with local volume default, S3/MinIO later | Keeps Compose simple while preserving a scaling path | API and worker must share the volume; S3 requires credentials/config |
| ADR-013 | No authentication in the MVP | Internal single-team tool; time is better spent on engine integration | Exposed deployments require a reverse proxy/auth layer before public use |
| ADR-014 | Persist run metadata/metrics always; trajectories optional artifacts | Keeps Postgres small and fast | Large historical trajectories may be unavailable unless artifact persistence is enabled |

---

## 13. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Uploaded Python executes arbitrary code | Critical | AST denylist, size limits, non-root worker container, no secrets/network in worker; document explicitly |
| `src` package name collision | Blocks integration | Runtime alias loader (validated); contract test for both imports |
| `NaN`/`Infinity` breaks JSON responses | Endpoint 500s | Central `json_safe` sanitizer; return `null` + `non_finite_metrics` |
| Reference Streamlit call order is wrong | Silent wrong optimization inputs | Adapter calls the documented engine signature; golden contract test |
| Loss of numeric precision at API boundary | Mismatched results | Cast NumPy scalars to Python floats consistently; test serialization |
| GA runs block API/worker resources | Poor latency or starvation | Celery worker with bounded concurrency; max wall clock; sync mode only for small runs |
| Queue backlog or stuck jobs | Users wait indefinitely | Queue depth alerts, `task_acks_late`, retry limits, hard time limits, cancel flag |
| Long-running requests hit proxy timeouts | Failed optimizations | Async jobs, SSE keepalive, nginx `proxy_read_timeout` |
| Artifact storage grows without bound | Disk exhaustion | Retention policy, cleanup task, content-addressed deduplication, volume monitoring |
| PostgreSQL migration drift | API/worker failures at startup | One-shot `migrate` service, readiness checks, CI migration test |
| PostgreSQL becomes a bottleneck | Slow history/list endpoints | Indexes, pagination, JSONB parsimony, connection pooling, read replicas later |
| Redis outage loses progress streams | SSE stops, jobs still run | Redis is not the source of truth; final state in Postgres; polling fallback and restart policy |
| Artifact/DB inconsistency | Missing code or orphan blobs | Write blob first, then DB row; cleanup detects orphans; shared volume in Compose |
| Duplicate optimization for one system | Wasted CPU | Redis distributed lock keyed by `system_id`; return `409 optimization_in_progress` |
| Engine drift over time | Broken endpoints | Contract tests against pinned engine commits; integrity script |
| Metric comparison confusion | User mistrust | Label engine, show workflow-specific results, explain non-finite values |

---

## 14. Assumptions and open questions

### Assumptions

1. The two repositories are vendored into the umbrella repo unchanged; their commits are pinned.
2. JSON case-study metadata is authoritative when a system is loaded from JSON.
3. The deployment uses PostgreSQL 16 and Redis 7 in Docker Compose; persistence is required and assumed.
4. GA optimization is PID-only.
5. Users accept that uploaded Python is not fully sandboxed in the MVP; the worker container is the isolation boundary.
6. The frontend is served behind nginx in production, so CORS is only a development concern.
7. Python 3.12, Node 20, PostgreSQL 16, and Redis 7 are acceptable runtime versions.
8. Artifact storage uses a shared local Docker volume in the first release; S3/MinIO is a drop-in adapter.
9. Run metadata and metrics are always persisted; full trajectory artifacts are optional and controlled by configuration.
10. Authentication and multi-tenancy are out of scope for the MVP.

### Open questions

1. Should the Ball Beam target be `0.0` (JSON `target`) or `0.1` (mentioned in the objective text)? Default: use the JSON machine-readable value and show the objective text separately.
2. Is production-grade sandboxing required in the first release? If yes, schedule the isolated worker phase before launch.
3. Should optimization support FSF? The engine does not; it would require changing `gaTunerPID` and is out of scope.
4. Should full trajectory artifacts be persisted by default, or only on demand? Current default: metadata/metrics always; trajectories optional.
5. Should progress streaming be SSE or WebSocket? SSE is simpler and sufficient for server → client events.
6. Are multi-user quotas/authentication needed? If yes, add `app/auth/`, per-client job limits, and container resource limits.
7. What are the retention periods for systems, runs, jobs, and artifacts? Default proposal: systems 24 h, jobs 1 h, runs 30 days, artifacts follow the owning run.
