"""Database engine and session management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from pv.models.base import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine(db_path: str | Path) -> Engine:
    """Create or return a cached SQLAlchemy engine."""
    global _engine
    if _engine is not None:
        return _engine
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path}"
    _engine = create_engine(url, echo=False)
    return _engine


def get_session_factory(db_path: str | Path) -> sessionmaker[Session]:
    """Return a session factory, creating the engine if needed."""
    global _session_factory
    if _session_factory is not None:
        return _session_factory
    engine = get_engine(db_path)
    _session_factory = sessionmaker(bind=engine)
    return _session_factory


def init_db(db_path: str | Path) -> None:
    """Create all tables if they don't exist."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)


def reset_engine() -> None:
    """Reset the cached engine and session factory. Used in tests."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
