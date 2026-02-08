"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pv.models.base import Base
from pv.services.prompt_service import PromptService


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Return a temporary database file path."""
    return tmp_path / "test.db"


@pytest.fixture()
def session(tmp_db: Path) -> Session:
    """Create an in-memory SQLite session with all tables."""
    engine = create_engine(f"sqlite:///{tmp_db}", echo=False)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess  # type: ignore[misc]
    sess.close()
    engine.dispose()


@pytest.fixture()
def service(session: Session) -> PromptService:
    """Return a PromptService bound to the test session."""
    return PromptService(session)
