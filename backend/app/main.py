from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.middleware import add_middleware as add_request_id_middleware
from app.api.v1 import health as health_router
from app.api.v1 import systems as systems_router
from app.context import AppContext
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import create_db_engine, create_session_factory
from app.domain.models import Capability
from app.infrastructure.redis import RedisClients, close_redis
from app.infrastructure.storage import create_storage
from app.infrastructure.storage.base import ArtifactStorage
from app.services.catalog_service import CatalogService
from app.services.cleanup_service import CleanupService
from app.services.system_service import SystemService

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.engines.loader import ga, load_engines, manual  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    context: AppContext = app.state.context
    configure_logging()
    logger.info(
        "startup_begin",
        app_env=context.settings.app_env,
        artifact_dir=str(context.settings.artifact_dir),
    )
    try:
        load_engines(
            ga_repo=context.settings.ga_engine_repo,
            manual_repo=context.settings.manual_engine_repo,
        )
        context.manual = dict(manual())
        context.ga = dict(ga())
        context.engines_loaded = True
        logger.info("engines_loaded", manual=sorted(context.manual), ga=sorted(context.ga))
    except Exception as exc:
        context.engines_loaded = False
        logger.error("engine_load_failed", error=str(exc))

    if context.cleanup_service is not None:
        try:
            context.cleanup_service.sweep_expired()
        except Exception as exc:
            logger.warning("startup_cleanup_failed", error=str(exc))

    try:
        yield
    finally:
        close_redis()
        if context.engine is not None:
            context.engine.dispose()
        logger.info("shutdown_complete")


def build_context(settings: Settings) -> AppContext:
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    storage: ArtifactStorage = create_storage(
        settings.artifact_backend, local_dir=str(settings.artifact_dir)
    )
    context = AppContext(settings=settings, redis=RedisClients(settings), storage=storage)
    context.engine = engine
    context.session_factory = session_factory
    context.catalog = CatalogService(repo_root=_REPO_ROOT)
    context.system_service = SystemService(
        session_factory=session_factory,
        storage=storage,
        storage_backend=settings.artifact_backend,
        catalog=context.catalog,
        max_upload_bytes=settings.max_upload_bytes,
        system_ttl_seconds=settings.system_ttl_seconds,
    )
    context.cleanup_service = CleanupService(system_service=context.system_service)
    return context


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    context = build_context(settings)

    app = FastAPI(
        title="Controller Tuner API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.context = context

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    add_request_id_middleware(app)
    register_error_handlers(app)
    app.include_router(health_router.router, prefix="/api/v1")
    app.include_router(systems_router.router, prefix="/api/v1")

    @app.get("/api/v1/capabilities", tags=["meta"])
    def capabilities() -> dict[str, list[str]]:
        return {"capabilities": [potential.value for potential in Capability]}

    return app


app = create_app()
