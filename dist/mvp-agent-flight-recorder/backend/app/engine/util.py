"""Small shared helpers for the engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
