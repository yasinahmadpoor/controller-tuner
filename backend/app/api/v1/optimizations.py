"""Synchronous GA optimization endpoints (Phase 4) and run history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.schemas import (
    OptimizationRunDetail,
    OptimizationRunListResponse,
    OptimizationRunSummary,
    OptimizeRequest,
    OptimizeResult,
    TargetHit,
)
from app.core.errors import InvalidMetadata
from app.domain.models import Engine, RunType
from app.services.optimization_service import OptimizationService

router = APIRouter(tags=["optimizations"])


def get_optimization_service(request: Request) -> OptimizationService:
    service = request.app.state.context.optimization_service  # type: ignore[attr-defined]
    if service is None:  # pragma: no cover - wired in lifespan
        raise InvalidMetadata("optimization service unavailable")
    return service


@router.post("/systems/{system_id}/optimize", response_model=OptimizeResult)
def optimize(system_id: str, payload: OptimizeRequest, request: Request) -> OptimizeResult:
    service = get_optimization_service(request)
    run, result = service.optimize(system_id, payload)
    return OptimizeResult(
        success=result["success"],
        run_id=run.id,
        engine=Engine.GA,
        controller_parameters=result["controller_parameters"],
        achieved_metrics=result["achieved_metrics"],
        ga_cost=result["ga_cost"],
        baseline_cost=result["baseline_cost"],
        progress=result["progress"],
        stop_reason=result["stop_reason"],
        num_evaluations=result["num_evaluations"],
        target_hit=TargetHit.model_validate(result["target_hit"]),
        warnings=result["warnings"],
        non_finite_metrics=result["non_finite_metrics"],
    )


@router.get(
    "/systems/{system_id}/optimizations",
    response_model=OptimizationRunListResponse,
)
def list_optimizations(
    system_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OptimizationRunListResponse:
    service = get_optimization_service(request)
    runs, total = service.list_runs(system_id, limit=limit, offset=offset)
    return OptimizationRunListResponse(
        items=[
            OptimizationRunSummary(
                run_id=run.id,
                system_id=run.system_id,
                run_type=RunType.OPTIMIZATION,
                engine=Engine(run.engine),
                status=run.status,
                stop_reason=run.stop_reason,
                duration_ms=run.duration_ms,
                created_at=run.created_at,
                summary={
                    key: (run.achieved_metrics or {}).get(key)
                    for key in ("mse", "settling_time", "overshoot", "control_effort")
                    if key in (run.achieved_metrics or {})
                },
                best_params=dict(run.best_params or {}),
            )
            for run in runs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/optimizations/{run_id}", response_model=OptimizationRunDetail)
def get_optimization(run_id: str, request: Request) -> OptimizationRunDetail:
    service = get_optimization_service(request)
    return OptimizationRunDetail.model_validate(service.get_run(run_id))


@router.delete("/optimizations/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_optimization(run_id: str, request: Request) -> None:
    service = get_optimization_service(request)
    service.delete_run(run_id)
