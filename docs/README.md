# Unified Controller Tuning Platform — Planning Docs

This folder contains the architecture and delivery plan for unifying the two provided engines:

- `gaTunerPID` — genetic-algorithm PID auto-tuning
- `tunerPID` — manual simulation and controller tuning

Both repositories are treated as **read-only**. The new platform adds a FastAPI backend, PostgreSQL + Redis persistence, Celery workers, a React + Tailwind frontend, Docker Compose deployment, and a test suite around them.

## Documents

| Document | What it covers |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Target architecture, engine integration strategy, canonical domain model, API contracts, frontend design, Docker/deployment, testing, security, risks, and ADRs |
| [`IMPLEMENTATION_PHASES.md`](./IMPLEMENTATION_PHASES.md) | Phased delivery plan with work items, deliverables, acceptance criteria, tests, estimates, milestones, and a demo script |
| [`API_EXAMPLES.md`](./API_EXAMPLES.md) | Copy-paste `curl` examples for catalog, systems, simulations, optimizations, jobs, and SSE |
| [`OPERATIONS.md`](./OPERATIONS.md) | Backups, migrations, queue recovery, retention, readiness, and troubleshooting |
| [`UPGRADING_ENGINES.md`](./UPGRADING_ENGINES.md) | Adding case studies and upgrading the read-only engine submodules |

## Key decisions in one page

1. **No engine modification.** All integration lives in a new backend layer.
2. **Runtime import isolation.** `tunerPID` is loaded as `manual_engine`; `gaTunerPID` keeps its native `src` package. This solves the `src` name collision without copying code.
3. **One canonical `SystemSpec`.** Both engine-specific configurations are derived from it.
4. **Two workflows, one UI.** Manual simulation uses `tunerPID`; GA optimization uses `gaTunerPID`.
5. **Engine-native metrics only.** The engines use different formulas; results are labeled by engine and are not compared across workflows.
6. **PostgreSQL + Redis persistence.** PostgreSQL stores systems, artifacts, simulation runs, optimization runs, and jobs. Redis provides the Celery broker, progress streams, distributed locks, and cache. TTL cleanup removes expired records and artifacts.
7. **Celery workers for async GA.** The API supports synchronous runs for scripts and Celery-backed jobs with SSE progress for the UI. The worker and API share an artifact volume (local now, S3/MinIO later).
8. **Explicit upload security.** AST validation and size limits in the MVP; the Celery worker container is the isolation boundary, with further sandboxing documented as production hardening.
9. **Nginx same-origin proxy.** No hard-coded container URLs and no production CORS.
10. **Contract tests protect the engines.** Seeded golden runs catch accidental behavior changes.
11. **Run history is a first-class feature.** Persisted simulations and optimizations can be listed, reopened, and deleted from the UI.

## Recommended first milestone

Complete Phases 0–4 in `IMPLEMENTATION_PHASES.md`, then build the manual UI (Phase 5). This proves both engines behind one API, with the database-backed system/run lifecycle, before expanding the frontend.
