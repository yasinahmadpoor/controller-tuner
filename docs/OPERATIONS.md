# Operations guide

## Backups

PostgreSQL is the system of record. Back up it plus the artifact volume.

```bash
docker compose exec -T postgres pg_dump -U tuner -d controller_tuner -Fc > controller_tuner.dump
docker run --rm -v controller-tuner_artifacts_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/artifacts.tgz -C /data .
```

Restore into an empty database, then restore the artifact volume before starting the
API/worker:

```bash
cat controller_tuner.dump | docker compose exec -T postgres pg_restore -U tuner -d controller_tuner --clean --if-exists
docker run --rm -v controller-tuner_artifacts_data:/data -v "$PWD":/backup alpine \
  sh -c 'rm -rf /data/* && tar xzf /backup/artifacts.tgz -C /data'
```

Redis is not authoritative for final state. Losing Redis loses queued tasks and live
progress streams; completed runs remain in PostgreSQL.

## Migrations

Migrations are one-shot in Compose (`migrate` service). Manual commands:

```bash
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic downgrade -1
```

Always back up before a downgrade. The current head is `0005_jobs`.

## Queue drain and recovery

```bash
docker compose stop worker beat
docker compose exec redis redis-cli LLEN ga
docker compose exec redis redis-cli --scan --pattern 'job:*' | head
docker compose start worker beat
```

- Cancel a job through `POST /jobs/{id}/cancel`; the worker checks the Redis cancel key
  between generations.
- Stale per-system locks expire automatically. To clear one after a confirmed worker
  crash: `docker compose exec redis redis-cli DEL lock:system:<system_id>:ga`.
- Delete expired jobs, runs, orphan artifacts, and TTL systems via Celery beat. To run
  cleanup now:

```bash
docker compose exec worker celery -A app.workers.celery_app:celery_app call app.workers.maintenance.cleanup_terminal_jobs
docker compose exec worker celery -A app.workers.celery_app:celery_app call app.workers.maintenance.cleanup_expired_runs
docker compose exec worker celery -A app.workers.celery_app:celery_app call app.workers.maintenance.cleanup_orphan_artifacts
```

## Readiness and logs

`GET /api/v1/ready` checks engines, PostgreSQL, Redis, Alembic head, and artifact
storage. The API does not become healthy in Compose until migrations finish. Logs are
structured JSON in production and include request IDs; worker logs include `job_id`.

```bash
docker compose logs -f backend worker beat
docker compose ps
```

## Retention settings

| Setting | Effect |
|---|---|
| `SYSTEM_TTL_SECONDS` | uploaded/inline systems expire |
| `JOB_RETENTION_SECONDS` | async job rows and Redis streams expire |
| `RUN_RETENTION_DAYS` | simulation/optimization history rows expire |

Deleting a system cascades its runs and jobs. Unreferenced artifacts are removed by
`cleanup_orphan_artifacts`.

## Troubleshooting

- **`service_not_ready` on async optimize** — Redis/Celery broker is unavailable or the
  queue could not accept the task. Check `docker compose ps redis worker`.
- **`optimization_in_progress`** — another GA job holds the per-system lock. Wait or
  clear a stale lock as above.
- **Readiness says migrations behind** — run the `migrate` service.
- **Charts missing when reopening history** — enable `PERSIST_TRAJECTORIES=true`; the
  detail endpoint requires `include_artifacts=true` (the UI sends it).
- **SSE stalls behind a proxy** — keep `proxy_buffering off` and a long
  `proxy_read_timeout`; the UI falls back to polling if the stream fails.
