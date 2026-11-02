"""ORM models for systems, artifacts, and later runs/jobs."""

from app.db.models.artifact import ArtifactModel
from app.db.models.system import SystemModel

__all__ = ["ArtifactModel", "SystemModel"]
