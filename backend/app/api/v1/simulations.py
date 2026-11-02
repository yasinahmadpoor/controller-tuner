"""Manual simulation endpoints (Phase 3): schema, simulate, and run history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.schemas import (
    ParamSchemaResponse,
    SimulateRequest,
    SimulateResult,
    SimulationRunDetail,
    SimulationRunListResponse,
    SimulationRunSummary,
)
from app.core.errors import InvalidMetadata
from app.domain.models import ControllerType, Engine, RunType
from app.services.simulation_service import SimulationService

router = APIRouter(tags=["simulations"])


def get_simulation_service(request: Request) -> SimulationService:
    service = request.app.state.context.simulation_service  # type: ignore[attr-defined]
    if service is None:  # pragma: no cover - wired in lifespan
        raise InvalidMetadata("simulation service unavailable")
    return service


@router.get("/systems/{system_id}/schema", response_model=ParamSchemaResponse)
def get_schema(
    system_id: str,
    request: Request,
    controller_type: Annotated[ControllerType, Query()] = ControllerType.PID,
) -> ParamSchemaResponse:
    service = get_simulation_service(request)
    payload = service.schema(system_id, controller_type)
    return ParamSchemaResponse.model_validate(payload)


@router.post("/systems/{system_id}/simulate", response_model=SimulateResult)
def simulate(system_id: str, payload: SimulateRequest, request: Request) -> SimulateResult:
    service = get_simulation_service(request)
    run, result = service.simulate(system_id, payload)
    return SimulateResult(
        success=True,
        run_id=run.id,
        engine=Engine.MANUAL,
        controller_type=payload.controller_type,
        params=dict(payload.params),
        time_points=result["time_points"],
        trajectory=result["trajectory"],
        control_signals=result["control_signals"],
        metrics=result["metrics"],
        non_finite_metrics=result["non_finite_metrics"],
    )


@router.get("/systems/{system_id}/simulations", response_model=SimulationRunListResponse)
def list_simulations(
    system_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SimulationRunListResponse:
    service = get_simulation_service(request)
    runs, total = service.list_runs(system_id, limit=limit, offset=offset)
    return SimulationRunListResponse(
        items=[
            SimulationRunSummary(
                run_id=run.id,
                system_id=run.system_id,
                run_type=RunType.SIMULATION,
                engine=Engine(run.engine),
                controller_type=ControllerType(run.controller_type),
                status=run.status,
                duration_ms=run.duration_ms,
                created_at=run.created_at,
                summary={
                    key: run.metrics.get(key)
                    for key in ("mse", "settling_time", "stable")
                    if key in (run.metrics or {})
                },
            )
            for run in runs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/simulations/{run_id}", response_model=SimulationRunDetail)
def get_simulation(
    run_id: str,
    request: Request,
    include_artifacts: Annotated[bool, Query()] = False,
) -> SimulationRunDetail:
    service = get_simulation_service(request)
    detail = service.get_run(run_id, include_artifacts=include_artifacts)
    return SimulationRunDetail.model_validate(detail)


@router.delete("/simulations/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulation(run_id: str, request: Request) -> None:
    service = get_simulation_service(request)
    service.delete_run(run_id)
