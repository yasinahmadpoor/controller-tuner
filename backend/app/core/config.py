from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: PostgresDsn = Field(
        default="postgresql+psycopg://tuner:tuner@localhost:5432/controller_tuner"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    ga_engine_repo: Path = _REPO_ROOT / "gaTunerPID"
    manual_engine_repo: Path = _REPO_ROOT / "tunerPID"

    artifact_dir: Path = _REPO_ROOT / "backend" / "data" / "artifacts"
    artifact_backend: str = "local"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    max_upload_bytes: int = 262_144
    max_request_bytes: int = 1_048_576
    system_ttl_seconds: int = 86_400
    job_retention_seconds: int = 3_600
    run_retention_days: int = 30

    max_concurrent_ga_jobs: int = 1
    ga_task_soft_time_limit: float = 180.0
    ga_task_time_limit: float = 240.0
    ga_queue_max_depth: int = 20

    uvicorn_workers: int = 1

    persist_trajectories: bool = False

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def alembic_ini_path(self) -> Path:
        return self.backend_root / "alembic.ini"

    @property
    def alembic_dir(self) -> Path:
        return self.backend_root / "alembic"

    @field_validator("artifact_backend")
    @classmethod
    def _artifact_backend_supported(cls, value: str) -> str:
        if value not in ("local", "s3"):
            raise ValueError("artifact_backend must be 'local' or 's3'")
        return value

    @field_validator("app_env")
    @classmethod
    def _app_env_known(cls, value: str) -> str:
        if value not in ("development", "test", "production"):
            raise ValueError(f"unknown APP_ENV: {value!r}")
        return value

    @field_validator("log_level")
    @classmethod
    def _log_level_known(cls, value: str) -> str:
        upper = value.upper()
        if upper not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"unknown LOG_LEVEL: {value!r}")
        return upper

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Clear the cached Settings; used by tests to pick up new env vars."""
    get_settings.cache_clear()


def reload_settings() -> Settings:
    reset_settings_cache()
    return get_settings()
