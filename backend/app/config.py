"""Runtime configuration, resolved from environment variables on each access.

Reading env at call time (instead of import time) keeps tests and embedded
usage simple: set the variable, call the function, no module reloads needed.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB_PATH = "afr.db"
DEFAULT_PORT = 8700
DEFAULT_REPLAY_MAX_EVENTS = 10_000
DEFAULT_REPLAY_TIMEOUT_SECONDS = 30.0


def db_path() -> str:
    return os.environ.get("AFR_DB_PATH", DEFAULT_DB_PATH)


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
    """Optional static bundle directory.

    AFR does not build or require a UI by default. Set AFR_UI_DIST only when a
    prebuilt static bundle should be served from the backend.
    """
    env = os.environ.get("AFR_UI_DIST")
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    p = Path(__file__).resolve().parent.parent.parent / "ui" / "dist"
    return p if p.is_dir() else None


# ---------------------------------------------------------------------------
# security / networking

# Safe CORS default: local AFR origins only, never "*" by default.
DEFAULT_DEV_ORIGINS = [
    "http://localhost:8700",
    "http://127.0.0.1:8700",
]


def cors_origins() -> list[str]:
    """Allowed CORS origins.

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


# ---------------------------------------------------------------------------
# replay readiness controls


def replay_enabled() -> bool:
    """Global runtime kill switch for replay. Default off.

    Only the literal values ``true``, ``1``, ``yes``, and ``on`` enable replay.
    """
    return os.environ.get("AFR_REPLAY_ENABLED", "").strip().lower() in (
        "true",
        "1",
        "yes",
        "on",
    )


def replay_max_events() -> int:
    """Maximum number of tool events a replay plan may contain.

    Falls back to ``AFR_REPLAY_MAX_OPERATIONS`` for backward compatibility.
    """
    raw = os.environ.get("AFR_REPLAY_MAX_EVENTS") or os.environ.get("AFR_REPLAY_MAX_OPERATIONS")
    if raw is None:
        return DEFAULT_REPLAY_MAX_EVENTS
    raw = raw.strip()
    if not raw:
        return DEFAULT_REPLAY_MAX_EVENTS
    value = int(raw)
    if value <= 0:
        raise ValueError("AFR_REPLAY_MAX_EVENTS must be a positive integer")
    return value


def replay_timeout_seconds() -> float:
    """Per-replay wall-clock timeout in seconds."""
    raw = os.environ.get("AFR_REPLAY_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_REPLAY_TIMEOUT_SECONDS
    raw = raw.strip()
    if not raw:
        return DEFAULT_REPLAY_TIMEOUT_SECONDS
    value = float(raw)
    if value <= 0:
        raise ValueError("AFR_REPLAY_TIMEOUT_SECONDS must be positive")
    return value
