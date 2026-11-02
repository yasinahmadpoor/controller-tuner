from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.api.schemas import (
    Capability,
    Engine,
    HealthResponse,
    ServiceStatus,
)
from app.context import AppContext

router = APIRouter(tags=["health"])


def get_context(request: Request) -> AppContext:
    return request.app.state.context


ContextDep = Annotated[AppContext, Depends(get_context)]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe — process is up and serving.",
)
def health(context: ContextDep) -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=None,
    summary="Readiness probe — engines, PostgreSQL, Redis, migrations, artifact storage.",
    responses={
        status.HTTP_200_OK: {"description": "All dependencies ready."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "One or more dependencies are not ready."
        },
    },
)
def ready(context: ContextDep) -> JSONResponse:
    checks: dict[str, ServiceStatus] = {
        "engines": ServiceStatus(ok=context.check_engine()),
        "postgres": ServiceStatus(ok=False),
        "redis": ServiceStatus(ok=False),
        "artifact_storage": ServiceStatus(ok=False),
        "migrations": ServiceStatus(ok=False),
    }

    db_ok, db_message = context.check_db()
    redis_ok, redis_message = context.check_redis()
    storage_ok, storage_message = context.check_storage()
    migrations_ok, migrations_message = context.check_migrations()

    checks["postgres"] = ServiceStatus(ok=db_ok, detail=db_message)
    checks["redis"] = ServiceStatus(ok=redis_ok, detail=redis_message)
    checks["artifact_storage"] = ServiceStatus(ok=storage_ok, detail=storage_message)
    checks["migrations"] = ServiceStatus(ok=migrations_ok, detail=migrations_message)

    payload: dict[str, Any] = {
        "status": "ready" if all(check.ok for check in checks.values()) else "not_ready",
        "checks": {name: status_model.model_dump() for name, status_model in checks.items()},
        "engines": {
            "manual": Engine.MANUAL.value if context.engines_loaded else None,
            "ga": Engine.GA.value if context.engines_loaded else None,
        },
        "capabilities": [capability.value for capability in list(Capability)],
    }

    ready_status = (
        status.HTTP_200_OK if payload["status"] == "ready" else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=ready_status, content=payload)
