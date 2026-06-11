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

EVENT_TYPES = (
    EVENT_MODEL_CALL,
    EVENT_TOOL_CALL,
    EVENT_STATE_SNAPSHOT,
    EVENT_CHECKPOINT,
    EVENT_LOG,
    EVENT_ERROR,
)

# Replay modes. MVP treats these as advisory strings passed to your handler;
# the Premium backend enforces them as safety policies.
MODE_DRY_RUN = "dry_run"
MODE_MOCK_TOOLS = "mock_tools"
MODE_ALLOW_SAFE_TOOLS = "allow_safe_tools"
MODE_ALLOW_SIDE_EFFECTS = "allow_side_effects"

REPLAY_MODES = (MODE_DRY_RUN, MODE_MOCK_TOOLS, MODE_ALLOW_SAFE_TOOLS, MODE_ALLOW_SIDE_EFFECTS)

# Tool replay policies (recorded on tool_call payloads, enforced by the
# premium policy engine during replay)
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


def jsonable(obj: Any) -> Any:
    """Coerce any object into JSON-safe data, repr()-ing what can't serialize."""
    try:
        return json.loads(json.dumps(obj, default=repr))
    except (TypeError, ValueError):
        return repr(obj)
