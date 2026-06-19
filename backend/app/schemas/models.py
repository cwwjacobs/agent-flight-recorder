"""Pydantic schemas for the AFR API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "model_call",
    "tool_call",
    "state_snapshot",
    "checkpoint",
    "log",
    "error",
    "replay_disabled",
    "replay_failed",
    "replay_limit_exhausted",
    "replay_rejected",
    "replay_started",
    "replay_action",
    "replay_completed",
]
EVENT_TYPES: tuple[str, ...] = (
    "model_call",
    "tool_call",
    "state_snapshot",
    "checkpoint",
    "log",
    "error",
    "replay_disabled",
    "replay_failed",
    "replay_limit_exhausted",
    "replay_rejected",
    "replay_started",
    "replay_action",
    "replay_completed",
)

RunStatus = Literal["running", "completed", "failed"]


# ---------------------------------------------------------------------------
# runs


class RunCreate(BaseModel):
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ForkRef(BaseModel):
    id: str
    name: str
    status: str
    fork_checkpoint_id: str | None = None
    created_at: str


class RunOut(BaseModel):
    id: str
    name: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    ended_at: str | None = None
    events_count: int = 0
    checkpoints_count: int = 0
    # run-list enrichment (GET /runs only; empty on single-run reads)
    last_error: str | None = None
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    # tags/notes/fork fields (always present; populated when used)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    parent_run_id: str | None = None
    fork_checkpoint_id: str | None = None
    forks: list[ForkRef] | None = None  # populated on GET /runs/{id} only


class RunUpdate(BaseModel):
    name: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class ForkIn(BaseModel):
    checkpoint_id: str
    name: str | None = None


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


ReplayMode = Literal["dry_run", "mock_tools", "allow_safe_tools", "allow_side_effects"]


class ReplayIn(BaseModel):
    checkpoint_id: str
    # dry_run and mock_tools are always on; allow_safe_tools / allow_side_effects
    # are opt-in advanced features. The default executes nothing.
    mode: ReplayMode = "dry_run"
    # required to unblock tools whose policy is requires_approval, and only
    # meaningful in allow_side_effects mode
    approved: bool = False


class ReplayOut(BaseModel):
    run_id: str
    checkpoint_id: str
    label: str | None = None
    mode: str
    state: dict[str, Any]
    status: str
    message: str
    replay_event_id: str
    # advanced replay policy engine output
    tool_plan: dict[str, dict[str, str]] = Field(default_factory=dict)
    mock_results: dict[str, Any] = Field(default_factory=dict)
    policy_notes: str | None = None
