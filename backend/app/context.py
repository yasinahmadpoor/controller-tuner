from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.models import OptimizationDefaults, SimulationDefaults
from app.infrastructure.redis import RedisClients
from app.infrastructure.storage.base import ArtifactStorage


@dataclass
class AppContext:
    """Runtime dependencies wired once at startup and shared by all routes."""

    settings: Any
    engine: Engine | None = None
    session_factory: sessionmaker[Session] | None = None
    redis: RedisClients | None = None
    storage: ArtifactStorage | None = None
    manual: dict[str, Any] = field(default_factory=dict)
    ga: dict[str, Any] = field(default_factory=dict)
    engines_loaded: bool = False
    catalog: Any = None
    system_service: Any = None
    cleanup_service: Any = None

    def check_engine(self) -> bool:
        return self.engines_loaded

    def check_db(self) -> tuple[bool, str]:
        if self.engine is None:
            return False, "database not configured"
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            return False, f"database unreachable: {exc}"
        return True, ""

    def check_redis(self) -> tuple[bool, str]:
        if self.redis is None:
            return False, "redis not configured"
        try:
            sync_redis = self.redis.sync()
            sync_redis.ping()
        except Exception as exc:
            return False, f"redis unreachable: {exc}"
        return True, ""

    def check_storage(self) -> tuple[bool, str]:
        if self.storage is None:
            return False, "artifact storage not configured"
        if not self.storage.writable():
            return False, f"artifact dir not writable: {self.storage.root_dir}"
        return True, ""

    def check_migrations(self) -> tuple[bool, str]:
        if self.engine is None:
            return False, "database not configured"
        try:
            from alembic.config import Config
            from alembic.runtime.migration import MigrationContext
            from alembic.script import ScriptDirectory
        except ImportError as exc:
            return False, f"alembic unavailable: {exc}"
        config_path = self.settings.alembic_ini_path  # type: ignore[attr-defined]
        if not config_path.exists():
            return False, f"alembic config missing at {config_path}"

        alembic_cfg = Config(str(config_path))
        alembic_cfg.set_main_option("script_location", str(self.settings.alembic_dir))
        try:
            with self.engine.connect() as conn:
                current = MigrationContext.configure(conn).get_current_revision()
            head = ScriptDirectory.from_config(alembic_cfg).get_current_head()
        except Exception as exc:
            return False, f"cannot inspect migrations: {exc}"

        if current is None:
            return False, "migrations pending"
        if current != head:
            return False, f"migrations behind: current={current}, head={head}"
        return True, ""

    def merge_simulation_defaults(
        self, defaults: SimulationDefaults, overrides: SimulationDefaults
    ) -> SimulationDefaults:
        """Overlay non-None request overrides onto the system's canonical defaults."""
        data = defaults.model_dump()
        data.update(
            {key: value for key, value in overrides.model_dump().items() if value is not None}
        )
        return SimulationDefaults.model_validate(data)

    def merge_optimization_defaults(
        self, defaults: OptimizationDefaults, overrides: dict[str, Any] | None
    ) -> OptimizationDefaults:
        """Overlay request-level optimization overrides onto canonical defaults."""
        if not overrides:
            return defaults
        data = defaults.model_dump()
        for key, value in overrides.items():
            if value is not None:
                data[key] = value
        return OptimizationDefaults.model_validate(data)
