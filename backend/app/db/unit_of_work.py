from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.db.repositories import (
    ArtifactRepository,
    JobRepository,
    OptimizationRunRepository,
    SimulationRunRepository,
    SystemRepository,
)


class UnitOfWork:
    """One transactional scope per request or Celery task.

    Repositories are wired here so services can commit related changes
    atomically (e.g. artifact row + system row).
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory
        self.session: Session | None = None
        self.systems: SystemRepository | None = None
        self.artifacts: ArtifactRepository | None = None
        self.simulation_runs: SimulationRunRepository | None = None
        self.optimization_runs: OptimizationRunRepository | None = None
        self.jobs: JobRepository | None = None
        # Convenience aliases used by some services/tests.
        self.simulations: SimulationRunRepository | None = None
        self.optimizations: OptimizationRunRepository | None = None

    def __enter__(self) -> UnitOfWork:
        self.session = self._session_factory()
        self._bind_repositories(self.session)
        return self

    def _bind_repositories(self, session: Session) -> None:
        self.systems = SystemRepository(session)
        self.artifacts = ArtifactRepository(session)
        self.simulation_runs = SimulationRunRepository(session)
        self.optimization_runs = OptimizationRunRepository(session)
        self.jobs = JobRepository(session)
        self.simulations = self.simulation_runs
        self.optimizations = self.optimization_runs

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
