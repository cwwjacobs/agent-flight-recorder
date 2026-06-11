"""Event ingest and timeline reads."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.errors import not_found_to_404
from app.engine import events as event_engine
from app.schemas import EventIn, EventOut

router = APIRouter(tags=["events"])


@router.post("/runs/{run_id}/events", response_model=EventOut, status_code=201)
def append_event(run_id: str, body: EventIn) -> dict:
    with not_found_to_404():
        return event_engine.append_event(
            run_id,
            event_type=body.event_type,
            name=body.name,
            payload=body.payload,
            created_at=body.created_at,
        )


@router.get("/runs/{run_id}/events", response_model=list[EventOut])
def list_events(
    run_id: str,
    event_type: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    with not_found_to_404():
        return event_engine.list_events(
            run_id, event_type=event_type, limit=limit, offset=offset
        )
