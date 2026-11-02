"""Synchronous GA optimization orchestration (Phase 4).

Validates the request against the system's optimization defaults and
capabilities, runs the GA engine in a fresh per-request instance, persists the
full result/progress, and exposes persisted optimization history.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import sessionmaker

from app.api.schemas import OptimizeRequest
from app.core.errors import (
    CapabilityNotSupported,
    EngineError,
    InvalidParameters,
    RunNotFound,
)
from app.db.models.optimization_run import OptimizationRunModel
from app.db.unit_of_work import UnitOfWork
from app.domain.models import Capability, Engine, SystemSpec
from app.engines.auto_tune_adapter import AutoTuneEngineAdapter
from app.services.simulation_service import _MaterializedCode
from app.services.system_service import SystemService

logger = logging.getLogger(__name__)

_GAIN_KEYS = ("Kp", "Ki", "Kd")


def _parse_run_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise RunNotFound(f"run {value!r} not found", context={"run_id": value}) from exc


class OptimizationService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        system_service: SystemService,
        run_retention_days: int = 30,
    ):
        self._session_factory = session_factory
        self._system_service = system_service
        self._run_retention_days = run_retention_days

    # ------------------------------------------------------------------ #
    # Optimization
    # ------------------------------------------------------------------ #
    def optimize(
        self, system_id: str, request: OptimizeRequest
    ) -> tuple[OptimizationRunModel, dict[str, Any]]:
        spec, code = self._system_service.get_spec_and_code(system_id)
        if Capability.OPTIMIZE not in spec.capabilities:
            raise CapabilityNotSupported(
                "system does not support optimization",
                context={"system_id": system_id},
            )
        if request.async_:
            raise InvalidParameters(
                "asynchronous optimization is not available until Phase 7",
                context={"async": True},
            )
        self._validate_request(spec, request)

        started_at = datetime.now(UTC)
        started = time.perf_counter()
        adapter = AutoTuneEngineAdapter()
        try:
            with _MaterializedCode(code) as code_path:
                result = adapter.optimize(spec, request, code_path=code_path)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._persist_run(
                spec=spec,
                request=request,
                status="failed",
                result=None,
                error={"type": type(exc).__name__, "message": str(exc)},
                started_at=started_at,
                duration_ms=duration_ms,
            )
            logger.exception("GA optimization failed", system_id=system_id)
            raise EngineError(f"GA optimization failed: {exc}") from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        run = self._persist_run(
            spec=spec,
            request=request,
            status="succeeded",
            result=result,
            error=None,
            started_at=started_at,
            duration_ms=duration_ms,
        )
        return run, result

    # ------------------------------------------------------------------ #
    # Run history
    # ------------------------------------------------------------------ #
    def list_runs(
        self, system_id: str, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[OptimizationRunModel], int]:
        spec = self._system_service.get(system_id)
        with UnitOfWork(self._session_factory) as uow:
            assert uow.optimization_runs is not None
            items, total = uow.optimization_runs.list(
                system_id=spec.system_id, limit=limit, offset=offset
            )
        return items, total

    def get_run(self, run_id: str) -> dict[str, Any]:
        parsed = _parse_run_uuid(run_id)
        with UnitOfWork(self._session_factory) as uow:
            assert uow.optimization_runs is not None
            run = uow.optimization_runs.get(parsed)
            if run is None:
                raise RunNotFound(f"run {run_id!r} not found", context={"run_id": run_id})
            return run.to_dict()

    def delete_run(self, run_id: str) -> None:
        parsed = _parse_run_uuid(run_id)
        with UnitOfWork(self._session_factory) as uow:
            assert uow.optimization_runs is not None
            if uow.optimization_runs.get(parsed) is None:
                raise RunNotFound(f"run {run_id!r} not found", context={"run_id": run_id})
            uow.optimization_runs.delete(parsed)
            uow.commit()

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def _validate_request(self, spec: SystemSpec, request: OptimizeRequest) -> None:
        defaults = spec.optimization
        ranges = dict(defaults.param_ranges)
        ranges.update(request.param_ranges or {})
        missing = sorted(set(_GAIN_KEYS) - set(ranges))
        if missing:
            raise InvalidParameters(
                "optimization requires gain ranges",
                context={"missing": missing},
            )
        for name, (low, high) in ranges.items():
            if low >= high:
                raise InvalidParameters(
                    f"parameter range for {name!r} must have low < high",
                    context={"param": name, "low": low, "high": high},
                )

        weights = dict(defaults.weights)
        weights.update(request.weights or {})
        for metric, weight in weights.items():
            if weight < 0:
                raise InvalidParameters(
                    f"weight for {metric!r} must be non-negative",
                    context={"metric": metric, "weight": weight},
                )

        fixed_targets = dict(defaults.fixed_targets)
        fixed_targets.update(request.fixed_targets or {})
        for metric, target in fixed_targets.items():
            if target <= 0:
                raise InvalidParameters(
                    f"fixed target for {metric!r} must be positive",
                    context={"metric": metric, "target": target},
                )

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _persist_run(
        self,
        *,
        spec: SystemSpec,
        request: OptimizeRequest,
        status: str,
        result: dict[str, Any] | None,
        error: dict[str, Any] | None,
        started_at: datetime,
        duration_ms: int,
    ) -> OptimizationRunModel:
        finished_at = datetime.now(UTC)
        expires_at = finished_at + timedelta(days=self._run_retention_days)
        payload = result or {}
        with UnitOfWork(self._session_factory) as uow:
            assert uow.optimization_runs is not None
            run = uow.optimization_runs.create(
                system_id=spec.system_id,
                engine=Engine.GA.value,
                status=status,
                request=request.model_dump(mode="json", by_alias=True),
                best_params=payload.get("controller_parameters", {}),
                achieved_metrics=payload.get("achieved_metrics", {}),
                progress=payload.get("progress", {}),
                stop_reason=payload.get("stop_reason"),
                num_evaluations=payload.get("num_evaluations"),
                target_hit=payload.get("target_hit"),
                warnings=payload.get("warnings", []),
                non_finite_metrics=payload.get("non_finite_metrics", []),
                ga_cost=payload.get("ga_cost"),
                baseline_cost=payload.get("baseline_cost"),
                error=error,
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=finished_at,
                expires_at=expires_at,
            )
            uow.commit()
        return run


__all__ = ["OptimizationService"]
