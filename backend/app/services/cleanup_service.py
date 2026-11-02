"""Startup cleanup sweep: remove expired systems and their orphaned blobs.

The scheduled Celery cleanup (beat) arrives in Phase 7; until then a sweep
runs once at API startup.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.services.system_service import SystemService

logger = logging.getLogger(__name__)


class CleanupService:
    def __init__(self, system_service: SystemService):
        self._system_service = system_service

    def sweep_expired(self) -> int:
        deleted = self._system_service.delete_expired(datetime.now(UTC))
        if deleted:
            logger.info("cleanup_removed_expired_systems", count=deleted)
        return deleted
