# Implementation Phases Plan

**Companion document:** `docs/ARCHITECTURE.md`  
**Goal:** Deliver the unified Controller Tuning Platform incrementally, with a working vertical slice at the end of every phase.  
**Constraint:** Do not modify `gaTunerPID/src/`, `tunerPID/src/`, or either repository's reference Streamlit app.

---

## 1. Delivery strategy

There are two ways to consume this plan:

### Track A — MVP vertical slice (recommended first pass)

Focus on Phases 0–6 plus minimal Docker and tests. This produces the full happy path:

```
load BallBeam (JSON or .py)
  → persist system + code artifact in PostgreSQL/artifact storage
  → manual simulate with PID gains (persisted run)
  → GA optimize with default ranges/targets (sync API; Celery/SSE in Track B)
  → inspect charts and metrics, reopen from history
  → run with docker compose up --build
```

Estimated effort: **11–15 focused days** for a robust version, or **~3–4 days** if the scope is compressed to the assignment-level minimum with a single database and no Celery UI.

### Track B — Production-ready platform

Complete all phases, including PostgreSQL + Redis persistence, Celery workers/SSE, hardening, CI, and comprehensive tests.

Estimated effort: **15–20 focused days**.

Estimates assume one full-stack developer familiar with FastAPI and React. Multiply by ~1.3 for unfamiliarity or review overhead.

### Phase dependency graph

```
Phase 0 (engine isolation)
   │
   ├──► Phase 1 (backend foundation + PostgreSQL/Redis/Alembic)
   │       │
   │       └──► Phase 2 (system ingestion + persistence + catalog)
   │               │
   │               ├──► Phase 3 (manual simulate + run history)
   │               │       │
   │               │       └──► Phase 5 (frontend manual + history) ─┐
   │               │                                                │
   │               └──► Phase 4 (GA optimize, sync + run history)    │
   │                       │                                         │
   │                       └──► Phase 6 (frontend auto-tune) ────────┤
   │                                                                 │
   │                               Phase 7 (Celery workers + SSE) ───┤
   │                                                                 │
   └──────────────────────────────► Phase 8 (Docker full stack) ◄────┘
                                           │
                                           └──► Phase 9 (hardening, CI, docs)
```

Phases 3 and 4 can overlap; Phases 5 and 6 can start once their respective backend endpoints are stable.

---

## 2. Global definition of done

A phase is not complete until:

- [ ] Code builds and runs locally.
- [ ] New behavior has automated tests.
- [ ] `ruff` passes for backend changes; `npm run lint` passes for frontend changes.
- [ ] No engine source files changed (`git diff` shows nothing under `gaTunerPID/src/`, `tunerPID/src/`).
- [ ] API changes are reflected in Pydantic models and the frontend types.
- [ ] Schema changes include an Alembic migration and are tested against an empty database.
- [ ] Error paths return the standard error envelope.
- [ ] Durable changes are written to PostgreSQL; transient progress lives in Redis.
- [ ] The phase's acceptance criteria are demonstrated with a command or a UI flow.
- [ ] Relevant documentation is updated.

---

## Phase 0 — Engine isolation and behavior baseline

**Goal:** Prove that both read-only engines can coexist in one backend process and capture their current behavior as a regression baseline.

**Prerequisites:** Both repositories present; Python environment with `numpy` and `pygad`.

### Work items

- [ ] Create the umbrella directory skeleton (`backend/`, `frontend/`, `docs/`, `scripts/`) without touching the two repositories.
- [ ] Implement `backend/app/engines/loader.py` with the `manual_engine` alias loader and native `src` loader.
- [ ] Write a small script that imports both engines and prints their classes.
- [ ] Capture golden outputs:
  - [ ] Manual engine: BallBeam PID (`Kp=15`, `Ki=0.5`, `Kd=2`, fixed IC `[1, 0]`, `dt=0.01`, `max_time=1.0`, limits `±0.5`). Record trajectory hash, first/last values, and metrics.
  - [ ] GA engine: BallBeam JSON with `max_time=1.0`, population 5, generations 2, seed 42, default ranges/targets. Record best gains, achieved metrics, progress length, stop reason.
- [ ] Store snapshots under `backend/tests/fixtures/golden/`.
- [ ] Add a `scripts/verify_engines.py` check that hashes the read-only engine files and compares them to a committed manifest.

### Deliverables

- `backend/app/engines/loader.py`
- `scripts/baseline.py` (or a pytest fixture generator)
- `backend/tests/fixtures/golden/*.json`
- `scripts/verify_engines.py`

### Acceptance criteria

- A single Python process can import both engines and run one simulation from each.
- The golden outputs are reproducible with the pinned dependency versions.
- The loader test fails loudly if either engine's public API changes.

### Tests

- `tests/contract/test_engine_imports.py` — both engines load.
- `tests/contract/test_manual_engine_contract.py` — deterministic BallBeam output.
- `tests/contract/test_ga_engine_contract.py` — deterministic seeded GA smoke run.

### Risks

- Import collision if the alias approach is misunderstood.
- PyGAD/numpy version drift. Pin versions before recording snapshots.

**Estimate:** 0.5–1 day.

---

## Phase 1 — Backend foundation

**Goal:** A runnable FastAPI skeleton with configuration, logging, error handling, health checks, canonical domain models, PostgreSQL sessions, Redis client, and Alembic migrations.

### Work items

- [ ] Create `backend/pyproject.toml` and pinned `requirements.txt` / `requirements-dev.txt`.
- [ ] Implement `app/main.py` with an app factory.
- [ ] Implement `app/core/config.py` using `pydantic-settings`:
  - [ ] `APP_ENV`, `LOG_LEVEL`
  - [ ] `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`
  - [ ] `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
  - [ ] `GA_ENGINE_REPO`, `MANUAL_ENGINE_REPO`
  - [ ] `ARTIFACT_DIR`, `ARTIFACT_BACKEND` (`local` | `s3`)
  - [ ] `CORS_ORIGINS`
  - [ ] `MAX_UPLOAD_BYTES`
  - [ ] `SYSTEM_TTL_SECONDS`, `JOB_RETENTION_SECONDS`, `RUN_RETENTION_DAYS`
  - [ ] `MAX_CONCURRENT_GA_JOBS`, `GA_TASK_SOFT_TIME_LIMIT`, `GA_TASK_TIME_LIMIT`
  - [ ] `UVICORN_WORKERS`
- [ ] Implement `app/db/base.py` with the SQLAlchemy declarative base.
- [ ] Implement `app/db/session.py` with engine/session factory and pool settings.
- [ ] Implement `app/db/unit_of_work.py` with repository wiring.
- [ ] Initialize Alembic (`backend/alembic/`, `alembic.ini`) and create an empty baseline migration.
- [ ] Implement `app/infrastructure/redis.py` with a shared client and health check.
- [ ] Implement `app/infrastructure/locks.py` with a Redis lock helper.
- [ ] Implement `app/infrastructure/storage/base.py` + `local.py`; add an `s3.py` stub.
- [ ] Implement structured logging with request IDs.
- [ ] Implement domain exceptions and the standard error envelope:
  - [ ] `SystemNotFound`, `RunNotFound`, `JobNotFound`, `UnsafeCode`, `InvalidMetadata`, `CapabilityNotSupported`, `JobQueueFull`, `OptimizationInProgress`, `EngineError`, `StorageError`, `ServiceNotReady`.
- [ ] Register exception handlers for domain errors and Pydantic validation errors.
- [ ] Add CORS middleware driven by settings.
- [ ] Add `/api/v1/health` and `/api/v1/ready`; readiness checks engines, PostgreSQL, Redis, migrations, and artifact storage.
- [ ] Load both engines at startup; set a readiness flag; do not re-import per request.
- [ ] Implement canonical domain models from `ARCHITECTURE.md §6.3` and Pydantic API schemas:
  - [ ] `SystemSpec`, `SimulationDefaults`, `OptimizationDefaults`
  - [ ] `CreateSystemRequest`, `SystemResponse`
  - [ ] `SimulateRequest`, `SimulateResult`
  - [ ] `OptimizeRequest`, `OptimizeResult`, `JobResponse`
  - [ ] `RunSummary`, `RunDetail`, `PaginatedResponse`
  - [ ] enums: `ControllerType`, `Engine`, `JobStatus`, `RunType`
- [ ] Implement the `json_safe` sanitizer and unit-test it with NumPy scalars, arrays, `NaN`, and `Infinity`.

### Deliverables

- Runnable backend: `uvicorn app.main:app --reload`.
- PostgreSQL session/UnitOfWork infrastructure and Alembic baseline.
- Redis client, lock helper, and local artifact storage.
- OpenAPI docs at `/docs`.
- Health and readiness endpoints.
- Canonical models and error envelope.

### Acceptance criteria

- `GET /api/v1/health` returns `200`.
- `GET /api/v1/ready` returns `200` only after engines load, PostgreSQL/Redis are reachable, migrations are current, and the artifact directory is writable.
- `GET /api/v1/ready` returns `503` with a specific reason when PostgreSQL or Redis is down.
- `alembic upgrade head` runs successfully against an empty database.
- Unknown routes return the FastAPI default 404 (acceptable) or the standard envelope (preferred).
- A deliberately thrown `SystemNotFound` returns `404` with `{"error": {"code": "system_not_found", ...}}`.
- The sanitizer converts `float("inf")` to `None` and `np.float64(1.0)` to `1.0`.

### Tests

- `tests/unit/test_config.py` — env parsing and defaults.
- `tests/unit/test_errors.py` — error mapping and status codes.
- `tests/unit/test_json_safe.py` — nested structures and non-finite values.
- `tests/unit/test_storage_local.py` — write/read/delete and path safety.
- `tests/integration/test_health.py` — health/readiness with DB/Redis up and down.
- `tests/integration/test_migrations.py` — `alembic upgrade head` from an empty schema.

**Estimate:** 0.5–1 day.

---

## Phase 2 — System ingestion and catalog

**Goal:** Create, normalize, and retrieve systems from both repositories' case studies and from user uploads.

### Work items

- [ ] Implement `CatalogService`:
  - [ ] Discover the three JSON case studies in `gaTunerPID/case_studies/json/`.
  - [ ] Discover the three `.py` case studies in `tunerPID/case_studies/`.
  - [ ] Merge them into curated catalog entries by slug (`ball_beam`, `dc_motor`, `inv_pendulum`).
  - [ ] Use JSON metadata as authoritative for target, limits, trim values, ICs, and fixed targets.
  - [ ] Expose `GET /api/v1/catalog`.
- [ ] Implement `app/db/models/system.py`, `artifact.py` and their repositories:
  - [ ] `SystemRepository`: create/get/list/delete with pagination.
  - [ ] `ArtifactRepository`: content-addressed create/get/delete-unreferenced.
  - [ ] Store metadata as JSONB; never store raw trajectory arrays in Postgres.
- [ ] Implement artifact storage flow in `SystemService`:
  - [ ] Validate and hash the code.
  - [ ] Write to `${ARTIFACT_DIR}/<sha256>.py` atomically (temp file + rename).
  - [ ] Deduplicate identical uploads by SHA-256.
  - [ ] Create the artifact row, then the system row in one Unit of Work.
  - [ ] On DB failure, delete the orphan blob.
- [ ] Add Alembic migration for `systems` and `artifacts`.
- [ ] Implement `app/core/security.py`:
  - [ ] Extension and size checks.
  - [ ] AST parse and denylist (imports, calls, dunder access, module-level infinite loops).
  - [ ] Require a top-level `dynamics` function.
  - [ ] Return clear, non-leaking error messages.
- [ ] Implement `SystemService.create_from_catalog(catalog_id)`:
  - [ ] Load the JSON profile if present; otherwise load the `.py` profile with curated metadata.
  - [ ] Store code via the artifact flow.
  - [ ] Load with the manual engine to auto-detect `num_states`.
  - [ ] Validate that detected states match JSON `num_states` when provided; if mismatch, return `400` with details.
  - [ ] Persist `SystemSpec` defaults in `systems.simulation_defaults` / `optimization_defaults`.
  - [ ] Set `capabilities=["simulate", "optimize"]`.
- [ ] Implement `SystemService.create_from_case_study_json(body)`:
  - [ ] Normalize scalar vs list `trim_values`.
  - [ ] Validate required fields.
  - [ ] Reuse the same artifact/persistence/detection path.
- [ ] Implement `SystemService.create_from_code(code, metadata)` and `create_from_upload(file, metadata)`:
  - [ ] Validate via AST.
  - [ ] Auto-detect `num_states`.
  - [ ] Auto-tune capability is enabled only when metadata provides the fields required to build the GA simulator config (`target`, control limits, channels, trim values, ICs).
  - [ ] If metadata is incomplete, default only where safe; otherwise return `422` explaining missing fields.
- [ ] Implement `SystemService.get/list/delete` with pagination and `404` for missing/deleted/expired rows.
- [ ] Implement `CleanupService.delete_system_artifacts` and a simple startup sweep; the scheduled Celery cleanup arrives in Phase 7.
- [ ] Implement:
  - [ ] `POST /api/v1/systems` (JSON modes A/B/C)
  - [ ] `POST /api/v1/systems` (multipart mode D)
  - [ ] `GET /api/v1/systems/{system_id}`
  - [ ] `GET /api/v1/systems?limit=&offset=&source_type=`
  - [ ] `DELETE /api/v1/systems/{system_id}` (cascade runs/jobs; remove unreferenced blobs)
- [ ] Never return `python_code`, `storage_key`, or artifact paths in responses.

### Deliverables

- Catalog endpoint.
- System creation from catalog, full JSON, inline code, and `.py` upload.
- PostgreSQL-backed system and artifact persistence.
- Canonical system metadata endpoint with pagination.
- Artifact deduplication and orphan cleanup on failure.

### Acceptance criteria

- `POST /systems` with `ball_beam` returns `201`, `num_states=2`, `target=0.0`, `capabilities` includes both workflows.
- `POST /systems` with the raw `BallBeam.json` content returns the same canonical metadata.
- Uploading `tunerPID/case_studies/BallBeam.py` with metadata returns `201` and auto-detected `num_states=2`.
- Uploading a file containing `import os` returns `400 unsafe_import`.
- `GET /systems/{id}` does not include source code, `storage_key`, or artifact paths.
- `GET /systems` returns paginated persisted rows.
- `DELETE` followed by `GET` returns `404`; related runs/jobs are cascade-deleted.
- Uploading identical code twice reuses the same artifact blob.
- A DB failure during creation leaves no orphan blob.
- An expired system is removed by the cleanup service (test with a short TTL).

### Tests

- `tests/unit/test_security.py` — accepted and rejected AST cases.
- `tests/unit/test_catalog.py` — catalog discovery and merge.
- `tests/unit/test_system_repository.py` — create/get/list/delete and pagination.
- `tests/unit/test_artifact_storage.py` — hashing, deduplication, orphan cleanup.
- `tests/integration/test_systems.py` — all creation modes, validation errors, deletion, DB persistence.
- `tests/integration/test_uploads.py` — multipart happy path and rejection paths.

**Estimate:** 1–1.5 days.

---

## Phase 3 — Manual simulation workflow

**Goal:** Expose the `tunerPID` engine over the API for schema-driven manual tuning and trajectory simulation.

### Work items

- [ ] Implement `ManualEngineAdapter`:
  - [ ] Build a fresh `DynamicalSystem` per request from the persisted artifact path and `SystemSpec`.
  - [ ] Apply `SimulationDefaults` and request overrides.
  - [ ] Apply `seed` with `numpy.random.seed` when provided.
  - [ ] Call `Simulator.evaluate(controller_type, params, fixed_initial_state)`.
  - [ ] Normalize output: plain lists, engine tag, `non_finite_metrics`.
- [ ] Add `app/db/models/simulation_run.py` + `SimulationRunRepository` and an Alembic migration.
- [ ] Persist a `simulation_runs` row for every simulation:
  - [ ] Store request, params, overrides, seed, metrics, warnings, duration, status.
  - [ ] Optionally write full trajectory arrays to artifact storage when `PERSIST_TRAJECTORIES=true`; store `trajectory_artifact_id`.
  - [ ] Return `run_id` in the response.
- [ ] Implement `GET /systems/{id}/schema?controller_type=...`:
  - [ ] Validate controller type against `P`, `PI`, `PD`, `PID`, `FSF`.
  - [ ] Return the engine's `get_param_schema` result.
- [ ] Implement `POST /systems/{id}/simulate`:
  - [ ] Validate that required gains are present for the controller type (e.g., `Ki` for `PI`/`PID`).
  - [ ] Reject unknown gain keys.
  - [ ] Reject `FSF` unless `K1..Kn` are provided.
  - [ ] Return `time_points`, `trajectory`, `control_signals`, `metrics`, and `run_id`.
- [ ] Implement run history endpoints:
  - [ ] `GET /systems/{id}/simulations` (paginated)
  - [ ] `GET /simulations/{run_id}`
  - [ ] `DELETE /simulations/{run_id}`
- [ ] Add request validation for override ranges (`dt > 0`, `max_time > 0`, `min_control < max_control`, channels within bounds).
- [ ] Optional: implement `POST /systems/{id}/simulate/batch` with `runs`, `seed`, and optional `initial_condition_range`; return per-run results or aggregate mean/std.

### Deliverables

- Schema endpoint.
- Manual simulation endpoint with persisted run history.
- Deterministic behavior when `initial_state` is provided and noise/disturbance are zero.

### Acceptance criteria

- Schema for `PID` returns `Kp`, `Ki`, `Kd` bounds.
- Schema for `FSF` returns `K1`, `K2` (for a 2-state system).
- BallBeam simulation with `Kp=15`, `Ki=0.5`, `Kd=2`, fixed IC `[1,0]`, `max_time=1.0` returns arrays of equal length, the expected metrics, and a `run_id`.
- A `simulation_runs` row stores the request and metrics.
- `GET /simulations/{run_id}` returns the persisted record after an API restart.
- `settling_time = Infinity` is serialized as `null` and listed in `non_finite_metrics`.
- Invalid controller type returns `422`.
- Unknown system ID returns `404`.
- Deleting the system cascade-deletes its simulation runs.

### Tests

- `tests/unit/test_manual_adapter.py` — config mapping, seed handling, normalization.
- `tests/unit/test_simulation_repository.py` — create/list/get/delete and cascade.
- `tests/integration/test_simulate.py` — happy path, FSF, invalid gains, non-finite metrics, 404, persisted history.

**Estimate:** 0.5–1 day.

---

## Phase 4 — GA optimization workflow (synchronous)

**Goal:** Expose the `gaTunerPID` engine over the API with the correct signature, validation, result normalization, and deterministic smoke tests.

### Work items

- [ ] Implement `AutoTuneEngineAdapter`:
  - [ ] Obtain the loaded dynamics callable from the manual engine loader.
  - [ ] Build the GA `SystemSimulator` config from `SystemSpec` (`dt`, `max_time`, target, channels, limits, trim values, trim ICs, dimensions).
  - [ ] Construct a fresh `GAOptimizer` per request.
  - [ ] Call `optimize_pid(weights=..., param_ranges=..., fixed_targets=...)` in the documented order.
  - [ ] Pass `max_wall_clock`.
  - [ ] Cast all numeric outputs to Python floats/ints and sanitize progress.
  - [ ] Add `engine: "ga_tuner"`, `target_hit`, `warnings`, and `non_finite_metrics`.
- [ ] Add `app/db/models/optimization_run.py` + `OptimizationRunRepository` and an Alembic migration.
- [ ] Implement `POST /systems/{id}/optimize` with `async: false`:
  - [ ] Validate ranges, weights, targets, and GA config.
  - [ ] Check the system has `optimize` capability.
  - [ ] Run synchronously in a bounded API thread.
  - [ ] Persist the request and final result, including full progress, stop reason, `target_hit`, and warnings.
  - [ ] Return `run_id`.
- [ ] Implement run history endpoints:
  - [ ] `GET /systems/{id}/optimizations` (paginated)
  - [ ] `GET /optimizations/{run_id}`
  - [ ] `DELETE /optimizations/{run_id}`
- [ ] Add validation caps:
  - [ ] population 5–200
  - [ ] generations 1–500
  - [ ] `max_wall_clock` 1–600 seconds
- [ ] Ensure the response includes every field the frontend needs:
  - [ ] `controller_parameters`
  - [ ] `achieved_metrics`
  - [ ] `ga_cost`, `baseline_cost`
  - [ ] `progress` (all engine fields)
  - [ ] `stop_reason`, `num_evaluations`, `target_hit`
- [ ] Optional: implement `POST /systems/{id}/trajectory` using `SystemSimulator.simulate_and_return_trajectory` for best-gain replay with N runs.
- [ ] Document the reference-app signature drift in the backend README and cover it with a contract test.

### Deliverables

- Synchronous GA optimization endpoint with persisted run history.
- Normalized GA result with progress history.
- Deterministic test using population 5 and 2 generations.

### Acceptance criteria

- BallBeam default optimization returns `controller_parameters`, `achieved_metrics`, `progress.iteration` of length equal to generations, `run_id`, and a valid `stop_reason`.
- An `optimization_runs` row stores the request, best params, metrics, progress, and stop reason.
- The same request with `seed=42` returns identical gains across runs.
- `progress` contains no `NaN`/`Infinity` and serializes successfully.
- An inverted range (`[50, 1]`) returns `422`.
- A system loaded without optimize capability returns `409`.
- `GET /optimizations/{run_id}` returns the persisted record after an API restart.
- The contract test asserts the adapter calls the engine with `(weights, param_ranges, fixed_targets)`.

### Tests

- `tests/unit/test_auto_tune_adapter.py` — config mapping, call-order contract, normalization.
- `tests/unit/test_optimization_repository.py` — create/list/get/delete and cascade.
- `tests/integration/test_optimize.py` — deterministic happy path, invalid input, capability conflict, 404, persisted history.
- `tests/contract/test_ga_engine_contract.py` — engine output shape remains as expected.

**Estimate:** 1–1.5 days.

---

## Phase 5 — Frontend shell and manual tuning UI

**Goal:** Deliver the first end-to-end browser flow: load a system, choose a controller, adjust gains, simulate, and inspect results.

### Work items

- [ ] Scaffold the React app with Vite + TypeScript.
- [ ] Configure Tailwind CSS and base design tokens.
- [ ] Set up routing and the app shell.
- [ ] Implement the typed API client with `VITE_API_URL`.
- [ ] Set up TanStack Query with sensible defaults (retry, stale time, error handling).
- [ ] Implement the catalog page:
  - [ ] Fetch `/catalog`.
  - [ ] Render case-study cards with name, states, target, capabilities.
  - [ ] Loading skeletons and empty/error states.
- [ ] Implement the upload dialog:
  - [ ] Drag-and-drop and file picker restricted to `.py`.
  - [ ] Metadata form (name, target, limits, channels, trim values, ICs, dt, max_time).
  - [ ] Submit multipart to `POST /systems`.
- [ ] Implement the workspace page:
  - [ ] Fetch `/systems/{id}`.
  - [ ] `SystemSummaryCard`.
  - [ ] Tabs: Manual, Auto-Tune (disabled until Phase 6), and History.
- [ ] Implement the manual tuning tab:
  - [ ] Controller type select.
  - [ ] Fetch schema and render sliders/inputs.
  - [ ] Preserve per-controller gain values in local state.
  - [ ] Advanced simulation settings (collapsible).
  - [ ] Optional fixed initial state input with validation.
  - [ ] Run button with loading and disabled state.
- [ ] Implement results:
  - [ ] Response chart with target reference line.
  - [ ] Control input chart.
  - [ ] Metrics panel with `∞` for `null` non-finite values.
  - [ ] Stability badge.
  - [ ] Show the persisted `run_id` and a "saved to history" indicator.
- [ ] Implement the History tab:
  - [ ] Fetch `/systems/{id}/simulations` with pagination.
  - [ ] List rows with timestamp, controller type, status, and key metrics.
  - [ ] Reopen a run by `run_id` and render its charts/metrics.
  - [ ] Delete a run with confirmation and cache invalidation.
- [ ] Add error banner and toast feedback.

### Deliverables

- Catalog, upload, workspace, manual tuning, manual results, and simulation history UI.
- Responsive layout.
- Loading and error states throughout.

### Acceptance criteria

- Loading `ball_beam` from the catalog opens the workspace.
- The PID sliders match the schema endpoint.
- Running a simulation displays both charts and all metrics, and a `run_id` is shown.
- The run appears in the History tab without a page reload.
- Reopening the run from history restores its charts and metrics.
- An unstable system shows the `Unstable` badge.
- A backend error shows a readable banner and re-enables the form.
- The page works at desktop and mobile widths.

### Tests

- `tests/components/CatalogPage.test.tsx` — cards and errors.
- `tests/components/UploadDialog.test.tsx` — file type validation.
- `tests/components/ManualTuningTab.test.tsx` — schema-driven sliders and submit states.
- `tests/components/TrajectoryChart.test.tsx` — renders with target line.
- `tests/components/RunHistoryList.test.tsx` — pagination, reopen, delete.
- `tests/hooks/useSimulate.test.ts` — success and error handling with MSW.
- `tests/hooks/useSystemRuns.test.ts` — list/pagination/delete with MSW.

**Estimate:** 1.5–2 days.

---

## Phase 6 — Frontend auto-tune UI and results

**Goal:** Deliver the second end-to-end browser flow: configure and run a GA optimization, then inspect gains, metrics, progress, and stop reason.

### Work items

- [ ] Build the auto-tune form:
  - [ ] Parameter range editor for `Kp`, `Ki`, `Kd` with low/high validation.
  - [ ] Targets and weights editor for `mse`, `settling_time`, `overshoot`, `control_effort`.
  - [ ] GA settings: population, generations, seed, max wall clock.
  - [ ] Pre-fill from the system's `optimization` defaults.
  - [ ] "Reset to case-study defaults" button.
- [ ] Add Zod schemas mirroring backend validation.
- [ ] Wire the optimize mutation to `POST /systems/{id}/optimize`.
- [ ] Handle synchronous mode first.
- [ ] Implement auto-tune results:
  - [ ] Best gains card.
  - [ ] Achieved metrics vs targets table with hit/miss indicators.
  - [ ] Stop reason badge (`normal`, `score_100`, `wall_clock`) with explanatory text.
  - [ ] `num_evaluations` and target-hit metadata.
  - [ ] Warnings panel.
- [ ] Implement progress charts:
  - [ ] Best vs mean cost per generation.
  - [ ] `Kp`, `Ki`, `Kd` per generation.
  - [ ] Success score and best score so far.
- [ ] Implement export:
  - [ ] Download gains as JSON.
  - [ ] Download gains as CSV.
- [ ] Extend the History tab with optimization runs:
  - [ ] Fetch `/systems/{id}/optimizations` with pagination.
  - [ ] Show best gains, stop reason, and `created_at`.
  - [ ] Reopen a run by `run_id` and render gains, metrics, and progress charts.
  - [ ] Delete an optimization run with confirmation.
- [ ] Optional: trajectory replay chart using the optional trajectory endpoint.
- [ ] Disable auto-tune for systems without the `optimize` capability and explain why.

### Deliverables

- Full auto-tune configuration and results UI.
- Progress and metrics visualizations.
- Export actions.
- Persisted optimization history with reopen/delete.

### Acceptance criteria

- Default BallBeam configuration runs successfully from the UI and returns a `run_id`.
- Validation blocks inverted ranges and negative weights before submitting.
- Results show gains, metrics, stop reason, and at least two progress charts.
- The optimization appears in History without a page reload and reopens with identical results.
- Export downloads valid JSON and CSV.
- Reset restores the system's defaults after edits.
- A failed optimization shows an error and preserves the form values.

### Tests

- `tests/components/AutoTuneForm.test.tsx` — defaults, validation, reset.
- `tests/components/AutoTuneResults.test.tsx` — gains, metrics table, stop reason.
- `tests/components/ProgressCharts.test.tsx` — renders from a fixture.
- `tests/components/OptimizationHistory.test.tsx` — list/reopen/delete.
- `tests/hooks/useOptimize.test.ts` — success, 422, 500.
- `tests/hooks/useOptimizationRuns.test.ts` — pagination/reopen with MSW.

**Estimate:** 1.5–2 days.

---

## Phase 7 — Celery jobs, progress streaming, and scheduling

**Goal:** Move long GA runs and maintenance work off the request path using Celery + Redis, stream generation progress over SSE, and support cancellation and retention.

### Work items

- [ ] Implement `app/workers/celery_app.py`:
  - [ ] Broker and result backend from settings.
  - [ ] Task routes: `ga` queue, `maintenance` queue.
  - [ ] `task_acks_late`, `worker_prefetch_multiplier=1`, `task_reject_on_worker_lost`.
  - [ ] Serializer allowlist (`json` only).
  - [ ] Soft/hard time limits from settings.
- [ ] Add `app/db/models/job.py` + `JobRepository` and an Alembic migration:
  - [ ] Fields per `ARCHITECTURE.md §6.7` (`id`, `run_id`, `run_type`, `status`, `progress`, `cancel_requested`, `worker_id`, `error`, timestamps, `expires_at`).
  - [ ] Allowed transitions enforced in the repository; terminal states are immutable.
- [ ] Implement the enqueue path in `POST /systems/{id}/optimize` when `async: true`:
  - [ ] Check the `ga` queue depth; return `429 job_queue_full` above the configured limit.
  - [ ] Acquire `lock:system:{id}:ga` (TTL, token release).
  - [ ] Reject with `409 optimization_in_progress` when locked.
  - [ ] Create the job/run rows, commit, then enqueue; on enqueue failure mark the job `failed`, release the lock, and return `503`.
  - [ ] Return `202` with `job_id`, `run_id`, `status_url`, `events_url`.
- [ ] Implement `app/workers/ga_tasks.py`:
  - [ ] Load job/run/system/artifact/request from PostgreSQL.
  - [ ] Mark the job `running` with the worker hostname.
  - [ ] Register the progress callback; unregister in `finally`.
  - [ ] Publish progress to a Redis Stream (`job:{job_id}:events`) with `MAXLEN ~ 1000`.
  - [ ] Check the cancel key (`job:{job_id}:cancel`) in the callback; raise `StopIteration` to stop PyGAD.
  - [ ] Persist the final `optimization_runs` row and update the job atomically.
  - [ ] Mark `cancelled` regardless of the engine's `stop_reason`.
  - [ ] Release the lock in a task `finally` block.
- [ ] Implement `GET /jobs/{job_id}` and `POST /jobs/{job_id}/cancel`:
  - [ ] Ownership checks via `job.run.system_id`.
  - [ ] Cancel is idempotent and writes the Redis cancel key plus `cancel_requested` in Postgres.
- [ ] Implement `GET /jobs/{job_id}/events` (SSE):
  - [ ] Use `redis.asyncio` `XREAD` blocking reads.
  - [ ] Send `Last-Event-ID` replay; close on terminal event.
  - [ ] Heartbeat comments every ~15s.
  - [ ] Terminal fallback: if the stream is missing but the DB says terminal, emit the terminal event.
- [ ] Implement maintenance tasks:
  - [ ] `cleanup_terminal_jobs` (expired jobs/streams).
  - [ ] `cleanup_expired_runs` honoring `RUN_RETENTION_DAYS`.
  - [ ] `cleanup_orphan_artifacts` for unreferenced blobs.
  - [ ] `delete_expired_systems` for TTL'd uploads.
  - [ ] Configure Celery beat schedules.
- [ ] Add worker readiness: `celery inspect ping` (healthcheck) and startup failure if the queue is unreachable.
- [ ] Frontend:
  - [ ] Default to async for long runs; keep sync available.
  - [ ] `useJob` polling hook with backoff.
  - [ ] `useJobEvents` SSE hook with polling fallback and `Last-Event-ID`.
  - [ ] Live progress panel (generation, score, gains, elapsed time).
  - [ ] Cancel button and `optimization_in_progress` handling.
  - [ ] Render final result through the same results components as Phase 6.
- [ ] Configure nginx for SSE (`proxy_buffering off`, long read timeout).

### Deliverables

- Celery worker + beat services.
- Durable job records in PostgreSQL.
- Redis Stream progress and SSE.
- Cancellation, retries, and retention tasks.
- Live progress UI.

### Acceptance criteria

- Async optimize returns `202` with `job_id`, `run_id`, and links; a job row exists.
- A second async optimize for the same system returns `409 optimization_in_progress`.
- A worker restart mid-run marks or retries the job; terminal states are never overwritten by late messages.
- Polling eventually returns `succeeded` with the same result shape as synchronous mode.
- SSE emits one event per generation and a terminal event; reconnect with `Last-Event-ID` replays missed events.
- Cancel transitions the job to `cancelled` and the UI stops the spinner.
- SSE failure in the browser falls back to polling.
- Beat runs cleanup tasks and expired runs/artifacts are removed.

### Tests

- `tests/unit/test_job_repository.py` — allowed/forbidden transitions.
- `tests/unit/test_locks.py` — acquire/release, contention, token safety.
- `tests/integration/test_jobs.py` — async happy path, polling, cancel, 409, 404, enqueue failure.
- `tests/integration/test_sse.py` — event ordering, `Last-Event-ID` replay, terminal fallback.
- `tests/integration/test_worker_tasks.py` — task success/failure/cancellation with a real Redis broker.
- `tests/integration/test_cleanup.py` — retention and orphan artifact cleanup.
- Frontend tests for the polling fallback and progress rendering.

**Estimate:** 2–3 days.

---

## Phase 8 — Docker Compose and deployment

**Goal:** Start the full platform with one command and validate it from outside the containers.

### Work items

- [ ] Write `backend/docker/backend.Dockerfile` (API + migrations) and `backend/docker/worker.Dockerfile` (worker + beat):
  - [ ] Python 3.12 slim and a shared base layer.
  - [ ] Pinned dependencies.
  - [ ] Copy backend and both engine repositories.
  - [ ] Non-root user.
  - [ ] API image gets a health check; worker/beat get `celery inspect ping` health checks.
- [ ] Write `backend/requirements.txt` with pinned versions (including `numpy`, `pygad`, `SQLAlchemy`, `alembic`, `psycopg`, `redis`, `celery`).
- [ ] Write `frontend/Dockerfile`:
  - [ ] Node 20 build stage.
  - [ ] Nginx runtime stage.
  - [ ] `VITE_API_URL=/api/v1`.
- [ ] Write `frontend/nginx.conf`:
  - [ ] SPA fallback.
  - [ ] `/api/` proxy to `http://backend:8000/api/`.
  - [ ] SSE-friendly settings.
- [ ] Write `docker-compose.yml`:
  - [ ] `postgres:16` with a named data volume and `pg_isready` healthcheck.
  - [ ] `redis:7` with `appendonly yes`, a named data volume, and `redis-cli ping` healthcheck.
  - [ ] `migrate` one-shot service running `alembic upgrade head`.
  - [ ] `backend` service depending on `postgres`, `redis`, and `migrate` (completed successfully).
  - [ ] `worker` service from `worker.Dockerfile` for the `ga` and `maintenance` queues.
  - [ ] `beat` service from `worker.Dockerfile` for maintenance schedules.
  - [ ] `frontend` service.
  - [ ] Shared artifact volume mounted in `backend`, `worker`, and `beat`.
  - [ ] Environment variables (`DATABASE_URL`, `REDIS_URL`, `CELERY_*`, `ARTIFACT_DIR`, retention, concurrency).
  - [ ] Ports `8000` and `3000`.
- [ ] Write `docker-compose.dev.yml`:
  - [ ] Bind mounts for hot reload.
  - [ ] Vite dev server on `5173`.
  - [ ] CORS for the dev origin.
  - [ ] Celery worker with `--reload` or manual restart instructions.
- [ ] Add `.dockerignore` files.
- [ ] Write `scripts/e2e_smoke.py`:
  - [ ] Hit health and readiness (DB/Redis/migrations/artifacts).
  - [ ] Create BallBeam from the catalog.
  - [ ] Run a manual simulation and fetch it from history.
  - [ ] Run a tiny GA optimization (sync) and fetch it from history.
  - [ ] Run an async optimization and consume SSE until terminal.
  - [ ] Assert response fields and that DB rows/artifact blobs exist.
- [ ] Write the root `README.md` with run instructions, assumptions, and known limitations.
- [ ] Compose profiles: default production-like; `dev` profile for hot reload.

### Deliverables

- Working Docker images for API and worker.
- Postgres, Redis, migrate, worker, beat, backend, and frontend Compose services.
- Production and development Compose files.
- Smoke test script.
- Root README.

### Acceptance criteria

- `docker compose up --build` starts all services cleanly.
- `migrate` exits 0 and the database has the expected tables.
- Backend readiness passes only when Postgres, Redis, migrations, and artifact storage are healthy; frontend waits for it.
- The UI loads at `http://localhost:3000`.
- The frontend reaches the backend through nginx without CORS errors.
- An async optimization runs on the worker and progress reaches the browser via SSE.
- `scripts/e2e_smoke.py` passes against the Compose stack.
- `docker compose down -v` cleans up without errors.
- No hard-coded container IPs anywhere.

### Tests

- Compose config validation (`docker compose config`).
- Smoke test in CI.
- Worker/beat container health checks.
- Manual browser check of the happy path.

**Estimate:** 1–1.5 days.

---

## Phase 9 — Hardening, test coverage, and documentation

**Goal:** Make the platform maintainable and safe enough for internal use, and document the known risks.

### Work items

- [ ] Expand security validation:
  - [ ] Unit tests for every denylisted construct.
  - [ ] Clear error messages without leaking internals.
  - [ ] Upload size enforcement at the proxy and app layers.
- [ ] Add resource guardrails:
  - [ ] Request size limits.
  - [ ] GA caps.
  - [ ] Celery queue depth limit and `429 job_queue_full`.
  - [ ] Per-system optimize lock and bounded worker concurrency.
  - [ ] System TTL and run retention.
- [ ] Add structured logging and request IDs across API, worker, and beat.
- [ ] Add `/ready` checks for engines, PostgreSQL, Redis, migrations, and artifact storage, plus startup failure behavior.
- [ ] Add operational tasks: DB backup/restore notes, migration rollback guidance, queue drain instructions, orphan artifact cleanup.
- [ ] Complete backend coverage:
  - [ ] Unit tests for adapters, normalizers, repositories, jobs, locks, storage, security.
  - [ ] Integration tests for every endpoint and error code against real Postgres/Redis.
  - [ ] Contract tests for both engines.
  - [ ] Migration tests from empty and from previous head.
- [ ] Complete frontend coverage:
  - [ ] Component tests for all major flows, including history and live progress.
  - [ ] MSW handlers for every endpoint used.
  - [ ] Optional Playwright happy path.
- [ ] Add CI workflow:
  - [ ] Postgres 16 and Redis 7 service containers.
  - [ ] `alembic upgrade head` before integration tests.
  - [ ] Backend lint, type check, tests, coverage threshold.
  - [ ] Frontend lint, tests, build.
  - [ ] Docker build, Compose up, and smoke test.
  - [ ] Engine integrity check.
- [ ] Add `scripts/verify_engines.py` to CI to prove the engines are unchanged.
- [ ] Write documentation:
  - [ ] Root README: quick start, architecture summary, assumptions, limitations.
  - [ ] API examples with `curl`.
  - [ ] Security note about uploaded Python.
  - [ ] Data model and migration guide (Alembic).
  - [ ] Operations guide: backups, retention, queue drain, Redis/Postgres recovery.
  - [ ] Troubleshooting section.
- [ ] Add a short "how to add a new case study" guide.
- [ ] Add a short "how to upgrade an engine" guide:
  - [ ] Pin the new commit.
  - [ ] Regenerate golden snapshots intentionally.
  - [ ] Review contract-test diffs.

### Deliverables

- CI pipeline.
- Coverage report.
- Security and operations documentation.
- Reproducible engine integrity check.

### Acceptance criteria

- CI is green on a clean checkout with Postgres and Redis services.
- `alembic upgrade head` succeeds from an empty database and integration tests run against it.
- Backend integration code coverage is at least 80%.
- The smoke test runs in CI and against a local Compose stack.
- `scripts/verify_engines.py` fails if an engine source file changes.
- The README answers: how to run, how to test, how to operate the DB/queue, what is not supported, and what the security limitations are.

**Estimate:** 1–1.5 days.

---

## 3. Milestones

| Milestone | Phases | Demonstrable outcome |
|---|---|---|
| **M0 — Engine proof** | 0 | Both engines load in one process; golden outputs exist |
| **M1 — Backend manual slice** | 1–3 | Create system → schema → simulate via API; runs persist |
| **M2 — Backend auto slice** | 4 | Create BallBeam → optimize GA via API; runs persist |
| **M3 — UI manual slice** | 5 | Browser: load → manual simulate → charts → history |
| **M4 — UI auto slice** | 6 | Browser: load → configure GA → results → history |
| **M5 — Deployable** | 8 | `docker compose up --build` works end to end with DB/Redis |
| **M6 — Production-ready** | 7, 9 | Celery progress/SSE, CI, hardening, docs |

Recommended review gates: **M1**, **M4**, **M5**. Do not start Phase 8 before M4 unless deployment feedback is needed early.

---

## 4. Suggested work breakdown by week

This is a suggested cadence, not a hard requirement.

### Week 1 — Foundation and systems

- Days 1–2: Phase 0 + Phase 1 (PostgreSQL, Redis, Alembic, storage).
- Days 3–5: Phase 2 (artifact persistence, catalog, ingestion).
- End-of-week demo: create systems from all three sources; persisted rows and deduplicated artifacts; catalog endpoint works.

### Week 2 — Both engine workflows

- Days 1–2: Phase 3 (simulate + run history).
- Days 3–5: Phase 4 (optimize + run history).
- End-of-week demo: manual simulate and GA optimize through the API with deterministic tests and persisted runs.

### Week 3 — Frontend

- Days 1–3: Phase 5.
- Days 4–5: Phase 6.
- End-of-week demo: full UI happy path locally, including history.

### Week 4 — Async jobs and streaming

- Days 1–4: Phase 7 (Celery, Redis Streams, SSE, cancellation, beat).
- Day 5: Phase 7 soak test and buffer.
- End-of-week demo: async optimization with live progress, cancellation, and cleanup.

### Week 5 — Docker, hardening, and handoff

- Days 1–2: Phase 8 (full Compose stack).
- Days 3–5: Phase 9, CI, docs, and buffer.
- End-of-week demo: `docker compose up --build` with Postgres/Redis/worker/beat plus CI green.

---

## 5. Test matrix

| Area | Unit | Integration | Contract | E2E |
|---|---|---|---|---|
| Engine imports | | | ✓ | |
| Manual simulation | ✓ | ✓ | ✓ | ✓ |
| GA optimization | ✓ | ✓ | ✓ | ✓ |
| System ingestion | ✓ | ✓ | | ✓ |
| Upload security | ✓ | ✓ | | |
| PostgreSQL repositories | ✓ | ✓ | | |
| Migrations (empty + upgrade) | | ✓ | | |
| Artifact storage/dedup | ✓ | ✓ | | |
| Redis locks | ✓ | ✓ | | |
| TTL/retention | ✓ | ✓ | | |
| Run history/reopen | ✓ | ✓ | | ✓ |
| Error envelope | ✓ | ✓ | | |
| Celery jobs/SSE (Phase 7) | ✓ | ✓ | | ✓ |
| Frontend forms | ✓ | | | ✓ |
| Frontend charts | ✓ | | | ✓ |
| Docker stack | | | | ✓ |

---

## 6. Demo script (acceptance run)

Use this script for milestone reviews and the final handoff.

1. From a clean checkout:

   ```bash
   docker compose up --build
   ```

2. Wait for the `migrate` service to exit 0 and for backend/worker/frontend health checks to pass.

3. Open `http://localhost:3000`.

4. Select **Ball Beam** from the catalog.

5. **Manual path:**
   - Choose `PID`.
   - Keep or adjust the gains.
   - Click **Run Simulation**.
   - Confirm the response chart, control chart, metrics, stability badge, and `run_id`.
   - Try an unstable gain set and confirm the badge and metrics update.
   - Open the **History** tab, reopen the run, and confirm the charts restore.

6. **Auto-tune path:**
   - Switch to the **Auto-Tune** tab.
   - Confirm defaults are pre-filled from `BallBeam.json`.
   - Use population 10, generations 5, seed 42 for a quick demo.
   - Click **Run Optimization**.
   - Confirm best gains, metrics vs targets, stop reason, progress charts, and `run_id`.
   - Export JSON and CSV.
   - Reopen the optimization from **History** and confirm identical results.
   - Click **Reset to Defaults** and confirm the form restores.

7. **Error path:**
   - Upload a `.py` file containing `import os`.
   - Confirm the backend rejects it with a readable error.
   - Start a second async optimization for the same system and confirm `409 optimization_in_progress`.

8. **Async path:**
   - Start a larger optimization in async mode.
   - Watch live progress over SSE and confirm generation events arrive.
   - Cancel it and confirm the job status becomes `cancelled`.
   - Restart the `worker` container mid-run and confirm the job resolves to a terminal state (retried or failed), not stuck.

9. **Persistence check:**

   ```bash
   docker compose exec postgres psql -U tuner -d tuner -c \
     "select count(*) from systems; select count(*) from optimization_runs;"
   ```

10. Tear down:

   ```bash
   docker compose down -v
   ```

---

## 7. Backlog (post-MVP)

| Item | Value | Notes |
|---|---|---|
| FSF gain optimization | Extends auto-tuning to full-state feedback | Requires engine changes; out of scope for the no-touch constraint |
| PostgreSQL HA / read replicas | Scale reads and survive DB failure | Managed Postgres or Patroni; app already uses a single URL |
| S3/MinIO artifact backend | Shared storage across nodes | Implement the existing `s3.py` adapter; drop the local volume |
| Dedicated worker images per engine | Blast-radius isolation | Separate queues/images; stronger sandbox for uploaded code |
| Isolated worker sandbox | Safer untrusted code execution | gVisor/Firecracker, no network, strict resource limits |
| Authentication, roles, and quotas | Multi-team usage | OIDC or internal SSO; add `owner_id` to rows |
| Batch parameter sweeps | Sensitivity analysis | New service layer on top of manual engine |
| Comparison mode | Side-by-side manual vs GA runs | Must label engines and avoid metric equivalence claims |
| Internationalization | Broader audience | UI-only concern |
| Dark mode | Preference | Tailwind theme tokens |
| Downloadable full report | Share results | Generate PDF/HTML from results + charts |

---

## 8. Engineering conventions

- **Branching:** one branch per phase (`phase-0-engine-isolation`, `phase-2-ingestion`, etc.), merged via squash merge or small PRs.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- **API changes:** update Pydantic models, OpenAPI output, and frontend types in the same change.
- **Schema changes:** never edit the DB by hand; add a reversible Alembic migration and a migration test in the same change.
- **Transactions:** write through the Unit of Work; commit before enqueueing Celery tasks; never enqueue inside an open transaction.
- **Tasks:** make Celery tasks idempotent and tolerant of redelivery; guard terminal job states; release locks in `finally`.
- **Engine changes:** none. If an engine bug blocks progress, document it, add a contract test that captures the behavior, and raise the issue upstream rather than patching the engine.
- **Test data:** use the provided case studies; do not create new dynamics files for tests unless absolutely necessary.
- **Timeouts:** keep integration tests fast by using `max_time=1.0`, population 5, and 2 generations.
- **Dependencies:** pin exact versions for engines and backend; use a lockfile for the frontend.

---

## 9. Phase exit checklist (copy per phase)

```
Phase: ____
Owner: ____
Branch: ____

[ ] Work items complete
[ ] Unit tests added and passing
[ ] Integration tests added and passing (real Postgres/Redis)
[ ] Contract tests passing (if engines involved)
[ ] Alembic migration added and tested from an empty DB
[ ] ruff / npm run lint clean
[ ] No changes under gaTunerPID/src or tunerPID/src
[ ] API docs / frontend types updated
[ ] Acceptance criteria demonstrated
[ ] README / docs updated
[ ] Reviewed and merged
```
