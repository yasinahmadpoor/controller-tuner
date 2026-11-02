"""Manual simulation orchestration (Phase 3).

Validates controller gains, builds a per-request manual engine system from the
persisted artifact, persists every run, and exposes persisted run history.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import sessionmaker

from app.api.schemas import SimulateRequest
from app.core.errors import EngineError, InvalidParameters, RunNotFound
from app.db.models.simulation_run import SimulationRunModel
from app.db.unit_of_work import UnitOfWork
from app.domain.models import Capability, ControllerType, Engine, SystemSpec
from app.engines.manual_adapter import (
    ManualEngineAdapter,
    merge_simulation_defaults,
)
from app.infrastructure.storage.base import ArtifactStorage
from app.services.system_service import SystemService

logger = logging.getLogger(__name__)

_PARAM_KEYS: dict[ControllerType, tuple[str, ...]] = {
    ControllerType.P: ("Kp",),
    ControllerType.PI: ("Kp", "Ki"),
    ControllerType.PD: ("Kp", "Kd"),
    ControllerType.PID: ("Kp", "Ki", "Kd"),
}


def _parse_run_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise RunNotFound(f"run {value!r} not found", context={"run_id": value}) from exc


def expected_param_keys(controller_type: ControllerType, num_states: int) -> tuple[str, ...]:
    if controller_type is ControllerType.FSF:
        return tuple(f"K{index}" for index in range(1, num_states + 1))
    return _PARAM_KEYS[controller_type]


class SimulationService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        system_service: SystemService,
        storage: ArtifactStorage,
        storage_backend: str,
        persist_trajectories: bool = False,
        run_retention_days: int = 30,
    ):
        self._session_factory = session_factory
        self._system_service = system_service
        self._storage = storage
        self._storage_backend = storage_backend
        self._persist_trajectories = persist_trajectories
        self._run_retention_days = run_retention_days

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #
    def schema(self, system_id: str, controller_type: ControllerType) -> dict[str, Any]:
        spec, code = self._system_service.get_spec_and_code(system_id)
        adapter = ManualEngineAdapter()
        with self._materialize(code) as code_path:
            params = adapter.schema(spec, controller_type, code_path=code_path)
        return {"controller_type": controller_type.value, "params": params}

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #
    def simulate(self, system_id: str, request: SimulateRequest) -> tuple[Any, dict[str, Any]]:
        spec, code = self._system_service.get_spec_and_code(system_id)
        if Capability.SIMULATE not in spec.capabilities:
            raise InvalidParameters(
                "system does not support simulation",
                context={"system_id": system_id},
            )
        merged = self._validate_request(spec, request)

        adapter = ManualEngineAdapter()
        started = time.perf_counter()
        try:
            with self._materialize(code) as code_path:
                payload = adapter.simulate(spec, request, code_path=code_path)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._persist_run(
                spec=spec,
                request=request,
                overrides=merged,
                status="failed",
                metrics={},
                non_finite_metrics=[],
                warnings=[],
                error={"type": type(exc).__name__, "message": str(exc)},
                duration_ms=duration_ms,
                trajectory=None,
            )
            logger.exception("manual simulation failed", system_id=system_id)
            raise EngineError(f"manual simulation failed: {exc}") from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        run = self._persist_run(
            spec=spec,
            request=request,
            overrides=merged,
            status="succeeded",
            metrics=payload["metrics"],
            non_finite_metrics=payload["non_finite_metrics"],
            warnings=[],
            error=None,
            duration_ms=duration_ms,
            trajectory=payload,
        )
        return run, payload

    # ------------------------------------------------------------------ #
    # Run history
    # ------------------------------------------------------------------ #
    def list_runs(
        self, system_id: str, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[SimulationRunModel], int]:
        spec = self._system_service.get(system_id)
        with UnitOfWork(self._session_factory) as uow:
            assert uow.simulation_runs is not None
            items, total = uow.simulation_runs.list(
                system_id=spec.system_id, limit=limit, offset=offset
            )
        return items, total

    def get_run(self, run_id: str, *, include_artifacts: bool = False) -> dict[str, Any]:
        parsed = _parse_run_uuid(run_id)
        with UnitOfWork(self._session_factory) as uow:
            assert uow.simulation_runs is not None
            run = uow.simulation_runs.get(parsed)
            if run is None:
                raise RunNotFound(f"run {run_id!r} not found", context={"run_id": run_id})
            detail = run.to_dict()
            trajectory = None
            if include_artifacts and run.trajectory_artifact_id is not None:
                assert uow.artifacts is not None
                artifact = uow.artifacts.get(run.trajectory_artifact_id)
                if artifact is not None:
                    try:
                        trajectory = json.loads(self._storage.open(artifact.storage_key))
                    except Exception:
                        logger.warning(
                            "trajectory artifact could not be read",
                            extra={"artifact_id": str(artifact.id)},
                        )
            detail["trajectory"] = trajectory
        return detail

    def delete_run(self, run_id: str) -> None:
        parsed = _parse_run_uuid(run_id)
        orphan_keys: list[str] = []
        with UnitOfWork(self._session_factory) as uow:
            assert uow.simulation_runs is not None
            run = uow.simulation_runs.get(parsed)
            if run is None:
                raise RunNotFound(f"run {run_id!r} not found", context={"run_id": run_id})
            uow.simulation_runs.delete(parsed)
            uow.session.flush()  # type: ignore[union-attr]
            assert uow.artifacts is not None
            orphans = uow.artifacts.delete_unreferenced()
            orphan_keys = [artifact.storage_key for artifact in orphans]
            uow.commit()
        self._delete_blobs(orphan_keys)

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def _validate_request(self, spec: SystemSpec, request: SimulateRequest):
        merged = merge_simulation_defaults(spec.simulation, request.overrides)
        self._validate_params(spec, request)
        self._validate_simulation(spec, merged)
        return merged

    def _validate_params(self, spec: SystemSpec, request: SimulateRequest) -> None:
        expected = expected_param_keys(request.controller_type, spec.num_states)
        provided = set(request.params)
        missing = sorted(set(expected) - provided)
        unknown = sorted(provided - set(expected))
        if missing or unknown:
            raise InvalidParameters(
                "controller parameters do not match the controller type",
                context={
                    "controller_type": request.controller_type.value,
                    "missing": missing,
                    "unknown": unknown,
                    "expected": list(expected),
                },
            )
        if request.initial_state is not None and len(request.initial_state) != spec.num_states:
            raise InvalidParameters(
                "initial_state length does not match the system order",
                context={
                    "expected": spec.num_states,
                    "got": len(request.initial_state),
                },
            )

    def _validate_simulation(self, spec: SystemSpec, simulation: Any) -> None:
        errors: dict[str, Any] = {}
        if simulation.dt <= 0:
            errors["dt"] = "must be > 0"
        if simulation.max_time <= 0:
            errors["max_time"] = "must be > 0"
        if simulation.min_control >= simulation.max_control:
            errors["control_limits"] = "min_control must be less than max_control"
        if not 0 <= simulation.input_channel < spec.num_inputs:
            errors["input_channel"] = f"must be in [0, {spec.num_inputs - 1}]"
        if not 0 <= simulation.output_channel < spec.num_states:
            errors["output_channel"] = f"must be in [0, {spec.num_states - 1}]"
        low, high = simulation.initial_condition_range
        if low > high:
            errors["initial_condition_range"] = "lower bound must be <= upper bound"
        if errors:
            raise InvalidParameters("simulation overrides are invalid", context={"errors": errors})

    # ------------------------------------------------------------------ #
    # Persistence helpers
    # ------------------------------------------------------------------ #
    def _persist_run(
        self,
        *,
        spec: SystemSpec,
        request: SimulateRequest,
        overrides: Any,
        status: str,
        metrics: dict[str, Any],
        non_finite_metrics: list[str],
        warnings: list[str],
        error: dict[str, Any] | None,
        duration_ms: int,
        trajectory: dict[str, Any] | None,
    ) -> SimulationRunModel:
        wrote_blob = False
        storage_key: str | None = None
        expires_at = datetime.now(UTC) + timedelta(days=self._run_retention_days)
        with UnitOfWork(self._session_factory) as uow:
            try:
                trajectory_artifact_id = None
                if self._persist_trajectories and trajectory is not None:
                    document = {
                        "time_points": trajectory.get("time_points", []),
                        "trajectory": trajectory.get("trajectory", []),
                        "control_signals": trajectory.get("control_signals", []),
                    }
                    data = json.dumps(document, allow_nan=False).encode("utf-8")
                    storage_key, wrote_blob = self._storage.write(data)
                    assert uow.artifacts is not None
                    artifact = uow.artifacts.create(
                        kind="trajectory",
                        storage_backend=self._storage_backend,
                        storage_key=storage_key,
                        sha256=_sha256(data),
                        size=len(data),
                        content_type="application/json",
                    )
                    uow.session.flush()  # type: ignore[union-attr]
                    trajectory_artifact_id = artifact.id

                assert uow.simulation_runs is not None
                run = uow.simulation_runs.create(
                    system_id=spec.system_id,
                    controller_type=request.controller_type.value,
                    request=request.model_dump(mode="json"),
                    params=dict(request.params),
                    overrides=overrides.model_dump(mode="json"),
                    initial_state=request.initial_state,
                    seed=request.seed,
                    engine=Engine.MANUAL.value,
                    status=status,
                    metrics=metrics,
                    non_finite_metrics=non_finite_metrics,
                    warnings=warnings,
                    error=error,
                    trajectory_artifact_id=trajectory_artifact_id,
                    duration_ms=duration_ms,
                    expires_at=expires_at,
                )
                uow.commit()
            except Exception:
                uow.rollback()
                if wrote_blob and storage_key is not None:
                    try:
                        self._storage.delete(storage_key)
                    except Exception:
                        logger.warning(
                            "orphan trajectory blob %s could not be removed", storage_key
                        )
                raise
        return run

    def _delete_blobs(self, storage_keys: list[str]) -> None:
        for key in storage_keys:
            try:
                self._storage.delete(key)
            except Exception:
                logger.warning("could not delete artifact blob %s", key)

    @staticmethod
    def _materialize(code: str):
        return _MaterializedCode(code)


class _MaterializedCode:
    """Write dynamics source to a temporary file for the engine loader."""

    def __init__(self, code: str):
        self._code = code
        self.path: Path | None = None

    def __enter__(self) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(self._code)
            self.path = Path(tmp.name)
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.path is not None:
            self.path.unlink(missing_ok=True)
            self.path = None


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


__all__ = ["SimulationService", "expected_param_keys"]
