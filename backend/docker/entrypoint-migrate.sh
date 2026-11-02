#!/bin/sh
set -eu

echo "Waiting for PostgreSQL..."
python - <<'PY'
import os
import time
import psycopg

url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
for attempt in range(60):
    try:
        with psycopg.connect(url, connect_timeout=3):
            print("PostgreSQL is reachable.")
            break
    except Exception as exc:
        if attempt == 59:
            raise SystemExit(f"PostgreSQL did not become ready: {exc}")
        time.sleep(1)
PY

echo "Running migrations..."
alembic upgrade head
echo "Migrations complete."
