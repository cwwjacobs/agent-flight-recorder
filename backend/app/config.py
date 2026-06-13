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


# ---------------------------------------------------------------------------
# security / networking

# Safe CORS default: the local dev UI origins only — never "*" by default, so a
# random website you have open can't read your recorded runs cross-origin.
DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8700",
    "http://127.0.0.1:8700",
]


def cors_origins() -> list[str]:
    """Allowed CORS origins. Default = local dev UI only.

    Set AFR_CORS_ORIGINS to a comma-separated list, or to "*" to explicitly
    (and knowingly) allow any origin. Empty/unset falls back to the safe default.
    """
    raw = os.environ.get("AFR_CORS_ORIGINS")
    if raw is None or not raw.strip():
        return list(DEFAULT_DEV_ORIGINS)
    raw = raw.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def api_token() -> str | None:
    """Optional bearer token. When unset, the API is unauthenticated (the
    zero-config localhost default). Set AFR_API_TOKEN to require auth on every
    API route — strongly recommended for any non-loopback deployment."""
    tok = os.environ.get("AFR_API_TOKEN", "").strip()
    return tok or None
