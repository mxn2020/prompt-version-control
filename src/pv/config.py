"""Platform-aware default paths for the pv database."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir

_DB_FILENAME = "pv.db"
_APP_NAME = "pv"


def default_db_path() -> Path:
    """Return the platform-appropriate default database path."""
    data_dir = Path(user_data_dir(_APP_NAME))
    return data_dir / _DB_FILENAME
