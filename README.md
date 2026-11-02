# Controller Tuner

Unified controller tuning platform: a FastAPI backend, Celery workers, PostgreSQL,
Redis, and a React + Tailwind UI wrapping the read-only `gaTunerPID` and `tunerPID`
engines.

## Quick start (production-like Compose)

Requirements: Docker Engine with Compose v2.

```bash
export POSTGRES_PASSWORD=tuner   # optional for local use; default is "tuner"
docker compose up --build
```

Open:

- UI: http://localhost:3000
- API: http://localhost:8000/api/v1
- API docs: http://localhost:8000/docs

Compose starts PostgreSQL, Redis, a one-shot migration job, the backend, a Celery
worker, Celery beat, and the nginx-served frontend. The backend becomes healthy only
after migrations complete and readiness checks pass.

Run the smoke test from the host:

```bash
python scripts/e2e_smoke.py
```

The Compose database is not published to the host by default. To also assert job/run
rows and artifact blobs, run the same script inside the backend container:

```bash
docker compose cp scripts/e2e_smoke.py backend:/tmp/e2e_smoke.py
docker compose exec backend sh -c \
  'API_URL=http://localhost:8000/api/v1 python /tmp/e2e_smoke.py'
```

Stop and clean up:

```bash
docker compose down
docker compose down -v   # also removes Postgres/Redis/artifact volumes
```

## Development Compose

The dev override mounts the backend and engine sources for hot reload, runs Vite on
port `5173`, and keeps the same Postgres/Redis/migrate/worker/beat services.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- UI: http://localhost:5173
- API: http://localhost:8000/api/v1

The Vite dev server uses `VITE_API_URL=http://localhost:8000/api/v1` and the backend
allows the `http://localhost:5173` origin.

## Local tests

Backend (uses Dockerized test Postgres and Redis):

```bash
cd backend
python -m pytest -q
ruff check app tests alembic
```

Frontend:

```bash
cd frontend
npm ci
npm test
npm run build
```

## Configuration

Copy `.env.example`-style values into the Compose environment as needed. Important
settings:

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | `tuner` | Compose Postgres password |
| `DATABASE_URL` | Compose-managed | PostgreSQL DSN (`postgresql+psycopg://...`) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis state, locks, progress streams |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | Celery result backend |
| `ARTIFACT_DIR` | `/data/artifacts` | Shared artifact volume |
| `PERSIST_TRAJECTORIES` | `true` in Compose | Store simulation chart data |
| `MAX_UPLOAD_BYTES` | `262144` | Python upload limit |
| `SYSTEM_TTL_SECONDS` | `86400` | Uploaded-system retention |
| `JOB_RETENTION_SECONDS` | `3600` | Async job retention |
| `RUN_RETENTION_DAYS` | `30` | Run history retention |
| `GA_QUEUE_MAX_DEPTH` | `20` | Queue-depth guard |
| `MAX_CONCURRENT_GA_JOBS` | `1` | Worker concurrency |
| `GA_TASK_SOFT_TIME_LIMIT` / `GA_TASK_TIME_LIMIT` | `180` / `240` | Celery limits |

## Architecture

- `backend/app/api/v1` — catalog, systems, simulations, optimizations, jobs.
- `backend/app/services` — orchestration, validation, persistence, async job state.
- `backend/app/engines` — adapters over the untouched engine repositories.
- `backend/app/workers` — Celery app, GA task, maintenance/cleanup tasks.
- `frontend/src` — typed API client, TanStack Query hooks, catalog/workspace UI.
- `docs/` — architecture, API plan, and implementation phases.

Engine sources are vendored into the images at `/app/engines/gaTunerPID` and
`/app/engines/tunerPID`. Set `GA_ENGINE_REPO`/`MANUAL_ENGINE_REPO` to override them.

## Known limitations

- **Uploaded Python is executed by the engines.** The MVP validates imports/AST and
  size, but it is not a real sandbox; only run trusted code.
- There is no authentication or per-user ownership in this phase.
- Artifact storage is local shared-volume only; the S3 backend is a stub.
- GA runs are CPU-bound and intentionally default to one worker process.
- Progress lives in Redis Streams; Redis loss stops live updates, but PostgreSQL
  remains the source of truth and the UI falls back to polling.
- The dev frontend container runs `npm ci` on every start and is not optimized for
  production; the default Compose file serves the nginx build.
