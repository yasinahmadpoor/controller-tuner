"""Worker-side dependency wiring shared by Celery tasks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory
from app.infrastructure.redis import RedisClients
from app.infrastructure.storage import create_storage
from app.infrastructure.storage.base import ArtifactStorage
from app.services.catalog_service import CatalogService
from app.services.optimization_service import OptimizationService
from app.services.system_service import SystemService

_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class WorkerRuntime:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    storage: ArtifactStorage
    redis: RedisClients
    system_service: SystemService
    optimization_service: OptimizationService

    def close(self) -> None:
        self.redis.close()
        self.engine.dispose()


def _catalog_root(settings: Settings) -> Path:
    ga_repo = Path(settings.ga_engine_repo)
    return ga_repo.parent if ga_repo.name == "gaTunerPID" else _REPO_ROOT


def build_worker_runtime(settings: Settings | None = None) -> WorkerRuntime:
    settings = settings or get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    storage = create_storage(settings.artifact_backend, local_dir=str(settings.artifact_dir))
    catalog = CatalogService(repo_root=_catalog_root(settings))
    system_service = SystemService(
        session_factory=session_factory,
        storage=storage,
        storage_backend=settings.artifact_backend,
        catalog=catalog,
        max_upload_bytes=settings.max_upload_bytes,
        system_ttl_seconds=settings.system_ttl_seconds,
    )
    optimization_service = OptimizationService(
        session_factory=session_factory,
        system_service=system_service,
        run_retention_days=settings.run_retention_days,
    )
    return WorkerRuntime(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        storage=storage,
        redis=RedisClients(settings),
        system_service=system_service,
        optimization_service=optimization_service,
    )
