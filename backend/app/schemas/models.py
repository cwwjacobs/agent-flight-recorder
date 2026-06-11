"""Pydantic schemas for the AFR API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal["model_call", "tool_call", "state_snapshot", "checkpoint", "log", "error"]
EVENT_TYPES: tuple[str, ...] = (
    "model_call",
    "tool_call",
    "state_snapshot",
    "checkpoint",
    "log",
    "error",
)

RunStatus = Literal["running", "completed", "failed"]


# ---------------------------------------------------------------------------
# runs


class RunCreate(BaseModel):
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunOut(BaseModel):
    id: str
    name: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    ended_at: str | None = None
    events_count: int = 0
    checkpoints_count: int = 0


class EndIn(BaseModel):
    status: Literal["completed", "failed"] = "completed"


# ---------------------------------------------------------------------------
# events


class EventIn(BaseModel):
    event_type: EventType
    name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None  # client-supplied timestamp (e.g. buffered ingest)


class EventOut(BaseModel):
    seq: int
    id: str
    run_id: str
    event_type: str
    name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


# ---------------------------------------------------------------------------
# checkpoints


class CheckpointIn(BaseModel):
    label: str | None = None
    # Explicit state. If omitted, state is reconstructed from state_snapshot
    # events recorded so far.
    state: dict[str, Any] | None = None


class CheckpointOut(BaseModel):
    id: str
    run_id: str
    event_id: str
    event_seq: int
    label: str | None = None
    created_at: str
    state: dict[str, Any] | None = None


class StateAtOut(BaseModel):
    run_id: str
    checkpoint: CheckpointOut
    state: dict[str, Any]
    source: Literal["checkpoint_table", "reconstructed"]


# ---------------------------------------------------------------------------
# replay


class ReplayIn(BaseModel):
    checkpoint_id: str
    # MVP contract: "dry_run" returns the reconstructed state without invoking
    # any handler. Other modes are passed through to the client-side resume
    # handler. Premium tightens this into a validated policy engine.
    mode: str = "dry_run"


class ReplayOut(BaseModel):
    run_id: str
    checkpoint_id: str
    label: str | None = None
    mode: str
    state: dict[str, Any]
    status: str
    message: str
    replay_event_id: str
