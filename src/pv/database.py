"""Database engine and session management."""

from __future__ import annotations

from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _alembic_cfg(db_url: str) -> AlembicConfig:
    """Build an Alembic Config pointing at the bundled migrations."""
    # alembic.ini lives at the project root; find it relative to this file
    pkg_dir = Path(__file__).resolve().parent  # src/pv
    project_root = pkg_dir.parent.parent  # repo root
    ini_path = project_root / "alembic.ini"
    cfg = AlembicConfig(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(project_root / "alembic"))
    return cfg


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
    """Initialise the database by running Alembic migrations to head.

    This is idempotent – safe to call multiple times.  It creates parent
    directories and the SQLite file as needed, then applies any pending
    Alembic migrations so that ``alembic_version`` is always present.
    """
    import logging

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine(db_path)
    db_url = f"sqlite:///{db_path}"
    cfg = _alembic_cfg(db_url)
    # Silence Alembic's INFO logging so it doesn't pollute CLI output.
    alembic_logger = logging.getLogger("alembic")
    prev_level = alembic_logger.level
    alembic_logger.setLevel(logging.WARNING)
    try:
        alembic_command.upgrade(cfg, "head")
    finally:
        alembic_logger.setLevel(prev_level)


def reset_engine() -> None:
    """Reset the cached engine and session factory. Used in tests."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
