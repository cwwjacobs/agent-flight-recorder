"""Runtime configuration, resolved from environment variables on each access.

Reading env at call time (instead of import time) keeps tests and embedded
usage simple: set the variable, call the function, no module reloads needed.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB_PATH = "afr.db"
DEFAULT_PORT = 8700


def db_path() -> str:
    return os.environ.get("AFR_DB_PATH", DEFAULT_DB_PATH)


def ui_dist_path() -> Path | None:
    """Directory with the built UI, if present. Served as static files."""
    env = os.environ.get("AFR_UI_DIST")
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    # repo layout default: backend/app/config.py -> ../../ui/dist
    p = Path(__file__).resolve().parent.parent.parent / "ui" / "dist"
    return p if p.is_dir() else None
