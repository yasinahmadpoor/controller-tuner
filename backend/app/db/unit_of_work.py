from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker


class BaseRepository:
    """Base class for repositories bound to a Session."""

    def __init__(self, session: Session):
        self.session = session


class SystemRepository(BaseRepository):
    """Persists and queries canonical system metadata (Phase 2)."""


class ArtifactRepository(BaseRepository):
    """Persists code/artifact metadata (content-addressed, Phase 2)."""


class RunRepository(BaseRepository):
    """Persists simulation and optimization runs (Phases 3/4)."""


class JobRepository(BaseRepository):
    """Persists async job records (Phase 7)."""


class UnitOfWork:
    """One transactional scope per request or Celery task.

    Repositories are wired here in Phase 1 so later phases only add queries —
    every repository shares one Session, letting a service commit related
    changes atomically (e.g. artifact row + system row).
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory
        self.session: Session | None = None
        self.systems = SystemRepository
        self.artifacts = ArtifactRepository
        self.runs = RunRepository
        self.jobs = JobRepository

    def __enter__(self) -> UnitOfWork:
        self.session = self._session_factory()
        self._bind_repositories(self.session)
        return self

    def _bind_repositories(self, session: Session) -> None:
        self.systems = SystemRepository(session)
        self.artifacts = ArtifactRepository(session)
        self.runs = RunRepository(session)
        self.jobs = JobRepository(session)

    def commit(self) -> None:
        if self.session is not None:
            self.session.commit()

    def rollback(self) -> None:
        if self.session is not None:
            self.session.rollback()

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.rollback()
        if self.session is not None:
            self.session.close()
            self.session = None

    @classmethod
    @contextmanager
    def from_factory(cls, session_factory: sessionmaker[Session]) -> Iterator[UnitOfWork]:
        with cls(session_factory) as uow:
            yield uow
