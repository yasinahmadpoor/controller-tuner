"""System ingestion and catalog service (Phase 2).

Creates, persists, and retrieves canonical systems. Shared flow for all
sources: security validation (user code), content-addressed artifact storage
with deduplication, `num_states` auto-detection through the manual engine,
then an atomic artifact row + system row commit. On database failure any
newly written blob is removed so failures never leave orphans.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import sessionmaker

from app.core.errors import (
    CatalogEntryNotFound,
    InvalidMetadata,
    InvalidPython,
    StorageError,
    SystemNotFound,
)
from app.core.security import validate_python_source
from app.db.models.system import SystemModel
from app.db.unit_of_work import UnitOfWork
from app.domain.models import (
    Capability,
    OptimizationDefaults,
    SimulationDefaults,
    SystemSource,
    SystemSpec,
)
from app.engines.loader import load_dynamics_from_code
from app.infrastructure.storage.base import ArtifactStorage
from app.services.catalog_service import CatalogService

logger = logging.getLogger(__name__)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise SystemNotFound(f"system {value!r} not found", context={"system_id": value}) from exc


class SystemService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        storage: ArtifactStorage,
        storage_backend: str,
        catalog: CatalogService,
        max_upload_bytes: int,
        system_ttl_seconds: int,
    ):
        self._session_factory = session_factory
        self._storage = storage
        self._storage_backend = storage_backend
        self._catalog = catalog
        self._max_upload_bytes = max_upload_bytes
        self._system_ttl_seconds = system_ttl_seconds

    # ------------------------------------------------------------------ #
    # Creation entry points
    # ------------------------------------------------------------------ #
    def create_from_catalog(self, catalog_id: str) -> SystemSpec:
        entry = self._catalog.get(catalog_id)
        if entry is None:
            raise CatalogEntryNotFound(
                f"catalog entry {catalog_id!r} not found",
                context={"catalog_id": catalog_id},
            )
        code = self._catalog.read_code(entry)
        if code is None:
            raise StorageError("catalog source code could not be read")
        validate_python_source(code)
        profile = self._catalog.read_json_profile(entry)
        if profile is not None:
            sim, opt, num_states = self._from_case_study_json(profile)
            num_inputs = int(profile.get("num_inputs", 1))
            return self._persist(
                code=code,
                sim=sim,
                opt=opt,
                name=entry.name,
                description=entry.description,
                objective=entry.objective,
                source_type=SystemSource.CATALOG_JSON,
                source_ref=entry.catalog_id,
                num_states_hint=num_states,
                ttl=False,
                optimize_enabled=True,
                num_inputs=num_inputs,
            )
        # Python-only case study: curated defaults apply.
        sim = SimulationDefaults()
        return self._persist(
            code=code,
            sim=sim,
            opt=OptimizationDefaults(),
            name=entry.name,
            description=entry.description,
            objective=entry.objective,
            source_type=SystemSource.CATALOG_PY,
            source_ref=entry.catalog_id,
            num_states_hint=None,
            ttl=False,
            optimize_enabled=False,
            num_inputs=1,
        )

    def create_from_case_study_json(self, case_study: dict[str, Any]) -> SystemSpec:
        code = case_study.get("python_code")
        if not isinstance(code, str) or not code.strip():
            raise InvalidMetadata("case study JSON must include a non-empty 'python_code' string")
        sim, opt, num_states = self._from_case_study_json(case_study)
        validate_python_source(code, max_bytes=self._max_upload_bytes)
        name = str(case_study.get("system_name") or "Case Study System")
        return self._persist(
            code=code,
            sim=sim,
            opt=opt,
            name=name,
            description=case_study.get("system_description"),
            objective=case_study.get("control_objective"),
            source_type=SystemSource.INLINE_JSON,
            source_ref=None,
            num_states_hint=num_states,
            ttl=True,
            optimize_enabled=True,
            num_inputs=int(case_study.get("num_inputs", 1)),
        )

    def create_from_code(self, code: str, metadata: dict[str, Any]) -> SystemSpec:
        validate_python_source(code, max_bytes=self._max_upload_bytes)
        sim, num_inputs, optimize_enabled = self._from_user_metadata(metadata)
        return self._persist(
            code=code,
            sim=sim,
            opt=OptimizationDefaults(),
            name=str(metadata.get("name", "Custom System")),
            description=metadata.get("description"),
            objective=metadata.get("objective"),
            source_type=SystemSource.INLINE_CODE,
            source_ref=None,
            num_states_hint=self._optional_int(metadata, "num_states"),
            ttl=True,
            optimize_enabled=optimize_enabled,
            num_inputs=num_inputs,
        )

    def create_from_upload(
        self, filename: str, content: bytes, metadata: dict[str, Any] | None
    ) -> SystemSpec:
        if not filename.endswith(".py"):
            raise InvalidMetadata("uploads must be .py files")
        try:
            code = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidPython("uploaded file must be valid UTF-8 Python source") from exc
        return self.create_from_code(code, metadata if metadata is not None else {})

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    def get(self, system_id: str) -> SystemSpec:
        parsed = _parse_uuid(system_id)
        with UnitOfWork(self._session_factory) as uow:
            system = self._systems(uow).get(parsed)
        if system is None:
            raise SystemNotFound(
                f"system {system_id!r} not found", context={"system_id": system_id}
            )
        return self._to_spec(system)

    def get_spec_and_code(self, system_id: str) -> tuple[SystemSpec, str]:
        """Return the canonical spec plus the persisted dynamics source."""
        parsed = _parse_uuid(system_id)
        with UnitOfWork(self._session_factory) as uow:
            system = self._systems(uow).get(parsed)
            if system is None:
                raise SystemNotFound(
                    f"system {system_id!r} not found", context={"system_id": system_id}
                )
            spec = self._to_spec(system)
            storage_key = system.artifact.storage_key
        try:
            data = self._storage.open(storage_key)
        except Exception as exc:
            raise StorageError(f"system code could not be read: {exc}") from exc
        try:
            code = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StorageError("system code is not valid UTF-8") from exc
        return spec, code

    def list(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        source_type: str | None = None,
        source_ref: str | None = None,
    ) -> tuple[list[SystemSpec], int]:
        with UnitOfWork(self._session_factory) as uow:
            items, total = self._systems(uow).list(
                limit=limit,
                offset=offset,
                source_type=source_type,
                source_ref=source_ref,
            )
        return [self._to_spec(system) for system in items], total

    # ------------------------------------------------------------------ #
    # Deletion
    # ------------------------------------------------------------------ #
    def delete(self, system_id: str) -> None:
        parsed = _parse_uuid(system_id)
        orphan_keys = self._delete_and_collect_orphans(parsed)
        self._delete_blobs(orphan_keys)

    def delete_expired(self, now: datetime) -> int:
        """Remove systems whose TTL elapsed; return how many were deleted."""
        with UnitOfWork(self._session_factory) as uow:
            expired = self._systems(uow).delete_expired(now)
            ids = [system.id for system in expired]
            for system_id in ids:
                self._systems(uow).delete(system_id)
            uow.commit()
        with UnitOfWork(self._session_factory) as uow:
            orphans = self._artifacts(uow).delete_unreferenced()
            orphan_keys = [artifact.storage_key for artifact in orphans]
            uow.commit()
        self._delete_blobs(orphan_keys)
        return len(ids)

    def _delete_and_collect_orphans(self, system_id: uuid.UUID) -> list[str]:
        with UnitOfWork(self._session_factory) as uow:
            if self._systems(uow).get(system_id) is None:
                raise SystemNotFound(
                    f"system {system_id} not found",
                    context={"system_id": str(system_id)},
                )
            self._systems(uow).delete(system_id)  # runs/jobs cascade at FK level
            orphans = self._artifacts(uow).delete_unreferenced()
            orphan_keys = [artifact.storage_key for artifact in orphans]
            uow.commit()
            return orphan_keys

    def _delete_blobs(self, storage_keys: list[str]) -> None:
        for key in storage_keys:
            try:
                self._storage.delete(key)
            except Exception:
                logger.warning("could not delete artifact blob %s", key)

    # ------------------------------------------------------------------ #
    # Metadata normalization
    # ------------------------------------------------------------------ #
    def _from_case_study_json(
        self, profile: dict[str, Any]
    ) -> tuple[SimulationDefaults, OptimizationDefaults, int | None]:
        sim_params = profile.get("simulation_params") or {}
        sim = SimulationDefaults(
            dt=float(sim_params.get("dt", 0.01)),
            max_time=float(sim_params.get("max_time", 10.0)),
            target=float(profile.get("target", 0.0)),
            input_channel=int(profile.get("input_channel", 0)),
            output_channel=int(profile.get("output_channel", 0)),
            trim_values=self._normalize_trim(profile.get("trim_values")),
            trim_ics=self._optional_floats(profile.get("trim_ics")),
            min_control=float(profile.get("min_ctrl", -10.0)),
            max_control=float(profile.get("max_ctrl", 10.0)),
        )
        raw_targets = profile.get("fixed_targets") or {}
        fixed_targets = {key: float(value) for key, value in raw_targets.items()}
        opt = (
            OptimizationDefaults(fixed_targets=fixed_targets)
            if fixed_targets
            else (OptimizationDefaults())
        )
        num_states = int(profile["num_states"]) if "num_states" in profile else None
        return sim, opt, num_states

    def _from_user_metadata(self, metadata: dict[str, Any]) -> tuple[SimulationDefaults, int, bool]:
        sim = SimulationDefaults(
            dt=float(metadata.get("dt", 0.01)),
            max_time=float(metadata.get("max_time", 10.0)),
            target=float(metadata.get("target", 0.0)),
            input_channel=int(metadata.get("input_channel", 0)),
            output_channel=int(metadata.get("output_channel", 0)),
            trim_values=self._normalize_trim(metadata.get("trim_values")),
            trim_ics=self._optional_floats(metadata.get("trim_ics")),
            min_control=float(metadata.get("min_control", -10.0)),
            max_control=float(metadata.get("max_control", 10.0)),
        )
        num_inputs = int(metadata.get("num_inputs", 1))
        # Optimize capability is enabled only when the metadata provides the
        # fields needed to build the GA simulator config.
        required = (
            "target",
            "min_control",
            "max_control",
            "input_channel",
            "output_channel",
            "trim_values",
            "trim_ics",
        )
        optimize_enabled = all(key in metadata for key in required)
        return sim, num_inputs, optimize_enabled

    def _normalize_trim(self, raw: Any) -> list[float]:
        if raw is None:
            return [0.0]
        if isinstance(raw, (list, tuple)):
            return [float(value) for value in raw]
        return [float(raw)]

    def _optional_floats(self, raw: Any) -> list[float] | None:
        if not raw:
            return None
        return [float(value) for value in raw]

    def _optional_int(self, metadata: dict[str, Any], key: str) -> int | None:
        if key not in metadata:
            return None
        return int(metadata[key])

    # ------------------------------------------------------------------ #
    # Persistence (shared flow)
    # ------------------------------------------------------------------ #
    def _persist(
        self,
        *,
        code: str,
        sim: SimulationDefaults,
        opt: OptimizationDefaults,
        name: str,
        description: str | None,
        objective: str | None,
        source_type: SystemSource,
        source_ref: str | None,
        num_states_hint: int | None,
        ttl: bool,
        optimize_enabled: bool,
        num_inputs: int = 1,
    ) -> SystemSpec:
        data = code.encode("utf-8")
        digest = _sha256(data)

        try:
            detected = int(load_dynamics_from_code(code, num_inputs=num_inputs).num_states)
        except ValueError as exc:
            raise InvalidPython(str(exc)) from exc
        except Exception as exc:
            raise InvalidPython(f"dynamics load failed: {exc}") from exc

        if num_states_hint is not None and num_states_hint != detected:
            raise InvalidMetadata(
                "detected num_states does not match the provided metadata",
                context={"provided": num_states_hint, "detected": detected},
            )

        expires_at = (
            datetime.now(UTC) + timedelta(seconds=self._system_ttl_seconds) if ttl else None
        )
        capabilities = [Capability.SIMULATE]
        if optimize_enabled:
            capabilities.append(Capability.OPTIMIZE)

        wrote_new_blob = False
        with UnitOfWork(self._session_factory) as uow:
            try:
                existing = self._artifacts(uow).by_sha256(digest)
                if existing is not None:
                    artifact_id = existing.id
                else:
                    storage_key, _ = self._storage.write(data)
                    wrote_new_blob = True
                    artifact = self._artifacts(uow).create(
                        kind="code",
                        storage_backend=self._storage_backend,
                        storage_key=storage_key,
                        sha256=digest,
                        size=len(data),
                        content_type="text/x-python",
                    )
                    self._flush(uow)
                    artifact_id = artifact.id

                system = self._systems(uow).create(
                    name=name,
                    description=description,
                    objective=objective,
                    source_type=source_type.value,
                    source_ref=source_ref,
                    num_states=detected,
                    num_inputs=num_inputs,
                    capabilities=[capability.value for capability in capabilities],
                    simulation_defaults=sim.model_dump(),
                    optimization_defaults=opt.model_dump(),
                    artifact_id=artifact_id,
                    code_sha256=digest,
                    code_size=len(data),
                    expires_at=expires_at,
                )
                spec = self._to_spec(system)
                uow.commit()
            except Exception:
                uow.rollback()
                if wrote_new_blob:
                    try:
                        self._storage.delete(storage_key)
                    except Exception:
                        logger.warning("orphan blob %s could not be removed", storage_key)
                raise
        return spec

    @staticmethod
    def _flush(uow: UnitOfWork) -> None:
        # Artifact rows must exist before the systems row can reference them.
        uow.session.flush()  # type: ignore[union-attr]

    def _systems(self, uow: UnitOfWork):
        assert uow.systems is not None
        return uow.systems

    def _artifacts(self, uow: UnitOfWork):
        assert uow.artifacts is not None
        return uow.artifacts

    def _to_spec(self, system: SystemModel) -> SystemSpec:
        return SystemSpec(
            system_id=system.id,
            name=system.name,
            description=system.description,
            objective=system.objective,
            source_type=SystemSource(system.source_type),
            source_ref=system.source_ref,
            num_states=system.num_states,
            num_inputs=system.num_inputs,
            capabilities=[Capability(capability) for capability in system.capabilities],
            simulation=SimulationDefaults.model_validate(system.simulation_defaults),
            optimization=OptimizationDefaults.model_validate(system.optimization_defaults),
            code_sha256=system.code_sha256,
            code_size=system.code_size,
            created_at=system.created_at,
        )
