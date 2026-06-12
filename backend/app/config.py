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


def api_token() -> str | None:
    """Optional bearer token. Unset (default) = open local instance."""
    token = os.environ.get("AFR_API_TOKEN", "").strip()
    return token or None


def cors_origins() -> list[str]:
    """Allowed CORS origins.

    AFR_CORS_ORIGINS is a comma-separated list. Defaults:
      - no auth token  -> ["*"]  (open local-dev behavior)
      - auth token set -> []     (same-origin only; no silent wildcard once
                                  the instance is meant to be protected)
    """
    raw = os.environ.get("AFR_CORS_ORIGINS", "").strip()
    if raw:  # blank counts as unset (docker-compose passes empty defaults)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [] if api_token() else ["*"]


def demo_seed_enabled() -> bool:
    """POST /demo/seed availability (default on — this is a local devtool;
    set AFR_DEMO_SEED_ENABLED=false on shared deployments)."""
    return os.environ.get("AFR_DEMO_SEED_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def ui_dist_path() -> Path | None:
    """Directory with the built UI, if present. Served as static files."""
    env = os.environ.get("AFR_UI_DIST")
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    # repo layout default: backend/app/config.py -> ../../ui/dist
    p = Path(__file__).resolve().parent.parent.parent / "ui" / "dist"
    return p if p.is_dir() else None
