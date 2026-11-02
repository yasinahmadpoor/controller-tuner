"""Async job polling, cancellation, and SSE progress endpoints (Phase 7)."""

from __future__ import annotations

import json
import time
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from redis.exceptions import TimeoutError as RedisTimeoutError
from starlette.concurrency import run_in_threadpool

from app.api.schemas import JobResponse
from app.infrastructure.progress import decode_entry, events_key

router = APIRouter(tags=["jobs"])

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def get_job_service(request: Request):
    return request.app.state.context.job_service


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, request: Request) -> JobResponse:
    service = get_job_service(request)
    return JobResponse.model_validate(service.get_job(job_id))


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, request: Request) -> JobResponse:
    service = get_job_service(request)
    return JobResponse.model_validate(service.cancel_job(job_id))


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    request: Request,
    last_event_id: Annotated[str | None, Query()] = None,
    last_event_header: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    service = get_job_service(request)
    snapshot = await run_in_threadpool(service.get_job, job_id)
    canonical_id = str(snapshot["job_id"])
    cursor = last_event_header or last_event_id or "0-0"

    async def event_stream():
        redis = request.app.state.context.redis.async_redis()  # type: ignore[attr-defined]
        current = cursor
        last_heartbeat = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            try:
                response = await redis.xread(
                    {events_key(canonical_id): current}, block=2_000, count=100
                )
            except RedisTimeoutError:
                response = None
            if response:
                for _stream, entries in response:
                    for entry in entries:
                        item = decode_entry(entry)
                        if item is None:
                            continue
                        current = item["id"]
                        payload = json.dumps(item["data"], allow_nan=False, separators=(",", ":"))
                        yield f"id: {current}\nevent: {item['event']}\ndata: {payload}\n\n"
                        if item["event"] == "done":
                            return
                continue

            latest = await run_in_threadpool(service.get_job, canonical_id)
            status = str(latest.get("status"))
            if status in TERMINAL_STATUSES:
                payload = json.dumps(
                    {"status": status, "job_id": canonical_id},
                    allow_nan=False,
                    separators=(",", ":"),
                )
                yield f"event: done\ndata: {payload}\n\n"
                return
            if time.monotonic() - last_heartbeat >= 15:
                last_heartbeat = time.monotonic()
                yield ": keepalive\n\n"

    headers: dict[str, Any] = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
