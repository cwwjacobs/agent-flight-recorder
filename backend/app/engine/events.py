"""Append-only event log."""

from __future__ import annotations

from typing import Any

from app.engine.runs import get_run
from app.engine.util import new_id, utcnow
from app.storage import repo


def append_event(
    run_id: str,
    event_type: str,
    name: str | None = None,
    payload: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict:
    """Append one event to a run's timeline.

    Appends are accepted even after a run has ended (late buffered events and
    replay bookkeeping are both legitimate post-end writes).
    """
    get_run(run_id)  # 404 if missing
    return repo.insert_event(
        event_id=new_id(),
        run_id=run_id,
        event_type=event_type,
        name=name,
        payload=payload or {},
        created_at=created_at or utcnow(),
    )


def list_events(
    run_id: str,
    event_type: str | None = None,
    limit: int = 1000,
    offset: int = 0,
    up_to_seq: int | None = None,
) -> list[dict]:
    get_run(run_id)
    return repo.list_events(
        run_id, event_type=event_type, limit=limit, offset=offset, up_to_seq=up_to_seq
    )
