"""Shared error translation: engine lookup errors -> HTTP 404."""

from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException

from app.engine.checkpoints import CheckpointNotFound
from app.engine.runs import RunNotFound


@contextmanager
def not_found_to_404():
    try:
        yield
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail=f"run not found: {exc}") from exc
    except CheckpointNotFound as exc:
        raise HTTPException(status_code=404, detail=f"checkpoint not found: {exc}") from exc
