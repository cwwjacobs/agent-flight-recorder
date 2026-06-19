"""Shared constants and JSON-safety helpers for the AFR SDK."""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_API_URL = "http://127.0.0.1:8700"

EVENT_MODEL_CALL = "model_call"
EVENT_TOOL_CALL = "tool_call"
EVENT_STATE_SNAPSHOT = "state_snapshot"
EVENT_CHECKPOINT = "checkpoint"
EVENT_LOG = "log"
EVENT_ERROR = "error"

EVENT_REPLAY_DISABLED = "replay_disabled"
EVENT_REPLAY_FAILED = "replay_failed"
EVENT_REPLAY_LIMIT_EXHAUSTED = "replay_limit_exhausted"
EVENT_REPLAY_REJECTED = "replay_rejected"
EVENT_REPLAY_STARTED = "replay_started"
EVENT_REPLAY_ACTION = "replay_action"
EVENT_REPLAY_COMPLETED = "replay_completed"

EVENT_TYPES = (
    EVENT_MODEL_CALL,
    EVENT_TOOL_CALL,
    EVENT_STATE_SNAPSHOT,
    EVENT_CHECKPOINT,
    EVENT_LOG,
    EVENT_ERROR,
    EVENT_REPLAY_DISABLED,
    EVENT_REPLAY_FAILED,
    EVENT_REPLAY_LIMIT_EXHAUSTED,
    EVENT_REPLAY_REJECTED,
    EVENT_REPLAY_STARTED,
    EVENT_REPLAY_ACTION,
    EVENT_REPLAY_COMPLETED,
)

# Replay modes. The base path treats these as advisory strings passed to your
# handler; the advanced (opt-in) backend enforces them as safety policies.
MODE_DRY_RUN = "dry_run"
MODE_MOCK_TOOLS = "mock_tools"
MODE_ALLOW_SAFE_TOOLS = "allow_safe_tools"
MODE_ALLOW_SIDE_EFFECTS = "allow_side_effects"

REPLAY_MODES = (MODE_DRY_RUN, MODE_MOCK_TOOLS, MODE_ALLOW_SAFE_TOOLS, MODE_ALLOW_SIDE_EFFECTS)

# Tool replay policies (recorded on tool_call payloads, enforced by the
# advanced replay policy engine during replay)
POLICY_SAFE = "safe"
POLICY_SIDE_EFFECTING = "side_effecting"
POLICY_MOCK_BY_DEFAULT = "mock_by_default"
POLICY_REQUIRES_APPROVAL = "requires_approval"

TOOL_POLICIES = (
    POLICY_SAFE,
    POLICY_SIDE_EFFECTING,
    POLICY_MOCK_BY_DEFAULT,
    POLICY_REQUIRES_APPROVAL,
)


def resolve_api_url(api_url: str | None = None) -> str:
    return api_url or os.environ.get("AFR_API_URL") or DEFAULT_API_URL


def resolve_api_token(token: str | None = None) -> str | None:
    """Bearer token for the backend, if any (explicit arg > AFR_API_TOKEN env)."""
    tok = token if token is not None else os.environ.get("AFR_API_TOKEN")
    tok = (tok or "").strip()
    return tok or None


def jsonable(obj: Any) -> Any:
    """Coerce any object into JSON-safe data, repr()-ing what can't serialize."""
    try:
        return json.loads(json.dumps(obj, default=repr))
    except (TypeError, ValueError):
        return repr(obj)
