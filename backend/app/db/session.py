from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return create_engine(
        str(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
