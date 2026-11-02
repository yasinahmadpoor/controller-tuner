from __future__ import annotations

import logging
import sys
from typing import Any

import structlog  # type: ignore[import-not-found]

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            (
                structlog.dev.ConsoleRenderer(colors=False)
                if settings.app_env == "development"
                else structlog.processors.JSONRenderer()
            ),
        ],
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name).bind(logger=name)
