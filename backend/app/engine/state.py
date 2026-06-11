"""State reconstruction.

State is derived by folding `state_snapshot` events in append (seq) order:

- mode "replace" (default): the snapshot becomes the new state
- mode "merge": the snapshot is deep-merged into the current state
  (dicts merge recursively; lists and scalars are replaced)

Folding by seq, not timestamp, makes reconstruction immune to clock skew in
client-supplied timestamps.
"""

from __future__ import annotations

from typing import Any

from app.storage import repo


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def fold_state(events: list[dict]) -> dict[str, Any]:
    """Fold a list of event dicts (in seq order) into a state dict."""
    state: dict[str, Any] = {}
    for event in events:
        if event.get("event_type") != "state_snapshot":
            continue
        payload = event.get("payload") or {}
        snapshot = payload.get("state")
        if not isinstance(snapshot, dict):
            continue
        if payload.get("mode") == "merge":
            state = _deep_merge(state, snapshot)
        else:
            state = snapshot
    return state


def reconstruct_state(run_id: str, up_to_seq: int | None = None) -> dict[str, Any]:
    """Reconstruct run state from recorded events, optionally up to a seq."""
    events = repo.list_events(
        run_id, event_type="state_snapshot", limit=1_000_000, up_to_seq=up_to_seq
    )
    return fold_state(events)
