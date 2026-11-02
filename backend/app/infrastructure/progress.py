"""Redis Stream helpers for GA progress and terminal events."""

from __future__ import annotations

import json
from typing import Any

from app.core.json_safe import json_safe


def events_key(job_id: str) -> str:
    return f"job:{job_id}:events"


def cancel_key(job_id: str) -> str:
    return f"job:{job_id}:cancel"


def publish_event(
    redis: Any,
    job_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    ttl_seconds: int | None = None,
) -> str:
    key = events_key(job_id)
    stream_id = redis.xadd(
        key,
        {"event": event_type, "data": json.dumps(json_safe(payload), separators=(",", ":"))},
        maxlen=1000,
        approximate=True,
    )
    if ttl_seconds is not None:
        redis.expire(key, max(1, int(ttl_seconds)))
    if isinstance(stream_id, bytes):
        stream_id = stream_id.decode("utf-8", errors="replace")
    return str(stream_id)


def publish_progress(
    redis: Any, job_id: str, event: dict[str, Any], *, ttl_seconds: int | None = None
) -> str:
    return publish_event(redis, job_id, "progress", event, ttl_seconds=ttl_seconds)


def publish_terminal(
    redis: Any,
    job_id: str,
    status: str,
    *,
    ttl_seconds: int | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {"status": status, "job_id": job_id}
    if extra:
        payload.update(extra)
    return publish_event(redis, job_id, "done", payload, ttl_seconds=ttl_seconds)


def decode_entry(entry: Any) -> dict[str, Any] | None:
    try:
        stream_id, fields = entry
    except (TypeError, ValueError):
        return None
    if isinstance(stream_id, bytes):
        stream_id = stream_id.decode("utf-8", errors="replace")
    raw = fields.get("data", fields.get(b"data"))
    event = fields.get("event", fields.get(b"event", b"progress"))
    if isinstance(event, bytes):
        event = event.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw) if isinstance(raw, (str, bytes)) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    return {"id": str(stream_id), "event": str(event), "data": payload}


def latest_event(redis: Any, job_id: str) -> dict[str, Any] | None:
    entries = redis.xrevrange(events_key(job_id), count=1)
    if not entries:
        return None
    return decode_entry(entries[0])


def read_events(
    redis: Any, job_id: str, last_id: str = "0-0", *, count: int = 100
) -> list[dict[str, Any]]:
    response = redis.xread({events_key(job_id): last_id}, count=count)
    if not response:
        return []
    decoded: list[dict[str, Any]] = []
    for _stream, entries in response:
        for entry in entries:
            item = decode_entry(entry)
            if item is not None:
                decoded.append(item)
    return decoded


def set_cancel_flag(redis: Any, job_id: str, *, ttl_seconds: int | None = None) -> None:
    key = cancel_key(job_id)
    redis.set(key, "1")
    if ttl_seconds is not None:
        redis.expire(key, max(1, int(ttl_seconds)))


def is_cancel_requested(redis: Any, job_id: str) -> bool:
    return bool(redis.exists(cancel_key(job_id)))


def clear_job_keys(redis: Any, job_id: str) -> None:
    redis.delete(events_key(job_id), cancel_key(job_id))
