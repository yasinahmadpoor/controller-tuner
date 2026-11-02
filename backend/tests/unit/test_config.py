from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings, reload_settings


def test_defaults_are_sensible():
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 10
    assert settings.max_upload_bytes == 262_144
    assert settings.artifact_backend == "local"
    assert settings.max_concurrent_ga_jobs == 1
    assert settings.run_retention_days == 30
    assert settings.system_ttl_seconds == 86_400
    assert settings.persist_trajectories in (True, False)


def test_env_overrides_apply(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")
    monkeypatch.setenv("ARTIFACT_BACKEND", "s3")
    monkeypatch.setenv("SYSTEM_TTL_SECONDS", "3600")
    monkeypatch.setenv("JOB_RETENTION_SECONDS", "600")
    monkeypatch.setenv("RUN_RETENTION_DAYS", "7")

    settings = Settings(_env_file=None)
    assert settings.app_env == "production"
    assert settings.log_level == "WARNING"
    assert settings.max_upload_bytes == 1024
    assert settings.artifact_backend == "s3"
    assert settings.system_ttl_seconds == 3600
    assert settings.job_retention_seconds == 600
    assert settings.run_retention_days == 7


@pytest.mark.parametrize(
    "field,value",
    [
        ("APP_ENV", "staging"),
        ("LOG_LEVEL", "verbose"),
        ("ARTIFACT_BACKEND", "gcs"),
    ],
)
def test_invalid_values_are_rejected(monkeypatch, field, value):
    monkeypatch.setenv(field, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_cors_origin_list_parses_commas(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, http://localhost:5173")
    settings = Settings(_env_file=None)
    assert settings.cors_origin_list == ["http://localhost:3000", "http://localhost:5173"]


def test_settings_cache_reload_picks_up_new_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "error")
    reload_settings()
    try:
        assert get_settings().log_level == "ERROR"
    finally:
        reload_settings()


def test_artifact_paths_default_inside_backend():
    settings = Settings(_env_file=None)
    root = Path(settings.artifact_dir)
    assert "artifacts" in root.parts
    assert "backend" in root.parts
