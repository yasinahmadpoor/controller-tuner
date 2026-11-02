#!/usr/bin/env python3
"""End-to-end smoke test for a running Compose stack.

Usage:
    python scripts/e2e_smoke.py
    API_URL=http://localhost:8000/api/v1 python scripts/e2e_smoke.py

The script uses only the standard library so it can run on the host or inside
any container. Optional ``DATABASE_URL``/``ARTIFACT_DIR`` environment variables
enable extra persistence/artifact assertions.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1").rstrip("/")


class SmokeFailure(RuntimeError):
    pass


def request(
    method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 60
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"{method} {path} -> {exc.code}: {body}") from exc


def expect(status: int, path: str, *, method: str = "GET", payload: dict | None = None) -> Any:
    actual, body = request(method, path, payload)
    if actual != status:
        raise SmokeFailure(f"{method} {path}: expected {status}, got {actual}: {body}")
    return body


def read_sse_until_done(job_id: str, timeout: float = 180) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{API_URL}/jobs/{job_id}/events", headers={"Accept": "text/event-stream"}
    )
    deadline = time.monotonic() + timeout
    event = None
    data: list[str] = []
    with urllib.request.urlopen(req, timeout=timeout) as response:
        for raw in response:
            if time.monotonic() > deadline:
                raise SmokeFailure("timed out waiting for SSE completion")
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data.append(line.split(":", 1)[1].strip())
            elif line == "":
                if event == "done":
                    return json.loads("\n".join(data) or "{}")
                event = None
                data = []
    raise SmokeFailure("SSE stream ended before a terminal event")


def assert_optional_persistence(job_id: str, run_id: str) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        try:
            import psycopg
        except ImportError:
            print("- DATABASE_URL set but psycopg is not installed; skipping DB assertion")
        else:
            url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
            with psycopg.connect(url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT status FROM jobs WHERE id = %s", (job_id,))
                    row = cur.fetchone()
                    if row is None:
                        raise SmokeFailure("async job row is missing from PostgreSQL")
                    cur.execute("SELECT status FROM optimization_runs WHERE id = %s", (run_id,))
                    run_row = cur.fetchone()
                    if run_row is None:
                        raise SmokeFailure("async optimization run row is missing")
            print("- PostgreSQL job/run rows exist")

    artifact_dir = os.environ.get("ARTIFACT_DIR")
    if artifact_dir and os.path.isdir(artifact_dir):
        blobs = [name for name in os.listdir(artifact_dir) if not name.endswith(".tmp")]
        if not blobs:
            raise SmokeFailure("artifact directory exists but contains no blobs")
        print(f"- Artifact directory contains {len(blobs)} blob(s)")


def main() -> int:
    print(f"Smoke testing {API_URL}")

    expect(200, "/health")
    ready_status, ready = request("GET", "/ready")
    if ready_status != 200 or ready.get("status") != "ready":
        raise SmokeFailure(f"readiness failed: {ready_status} {ready}")
    print("- health and readiness are OK")

    system = expect(
        201,
        "/systems",
        method="POST",
        payload={"source": {"type": "catalog", "catalog_id": "ball_beam"}},
    )
    system_id = system["system_id"]
    print(f"- created BallBeam system {system_id}")

    simulation = expect(
        200,
        f"/systems/{system_id}/simulate",
        method="POST",
        payload={
            "controller_type": "PID",
            "params": {"Kp": 15.0, "Ki": 0.5, "Kd": 2.0},
            "overrides": {"max_time": 1.0},
        },
    )
    run_id = simulation["run_id"]
    expect(200, f"/simulations/{run_id}")
    history = expect(200, f"/systems/{system_id}/simulations")
    if history["total"] < 1:
        raise SmokeFailure("manual simulation did not appear in history")
    print(f"- manual simulation persisted and re-opened ({run_id})")

    sync_opt = expect(
        200,
        f"/systems/{system_id}/optimize",
        method="POST",
        payload={
            "ga_config": {
                "population_size": 5,
                "generations": 2,
                "seed": 42,
                "max_wall_clock": 30,
            }
        },
    )
    expect(200, f"/optimizations/{sync_opt['run_id']}")
    print(f"- synchronous GA optimization persisted ({sync_opt['run_id']})")

    async_opt = expect(
        202,
        f"/systems/{system_id}/optimize",
        method="POST",
        payload={
            "async": True,
            "ga_config": {
                "population_size": 5,
                "generations": 2,
                "seed": 42,
                "max_wall_clock": 30,
            },
        },
    )
    job_id = async_opt["job_id"]
    done = read_sse_until_done(job_id)
    if done.get("status") != "succeeded":
        raise SmokeFailure(f"async job finished with {done.get('status')}")
    job = expect(200, f"/jobs/{job_id}")
    if job["status"] != "succeeded" or not job.get("result"):
        raise SmokeFailure("async job polling did not return a successful result")
    expect(200, f"/optimizations/{async_opt['run_id']}")
    print(f"- async GA job completed via SSE ({job_id})")

    assert_optional_persistence(job_id, async_opt["run_id"])
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
