"""Server-side replay preparation (see contract.py for the full contract).

Premium extends the MVP ticket with a per-tool safety plan computed by
policies.py — the safe-by-default matrix over recorded tool policies — plus
record/replay mock results (the last successful recorded result for every
tool the plan mocks). Free mode is restricted to the inherently safe modes
(dry_run, mock_tools).
"""

from __future__ import annotations

from typing import Any

from app import config
from app.engine import checkpoints as ckpt_engine
from app.engine import events as event_engine
from app.license import ensure_premium
from app.replay.contract import ReplayTicket
from app.replay.policies import FREE_MODES, MODES, ReplayLimitExhausted, build_tool_plan


class ReplayDisabled(Exception):
    """Raised when replay has been disabled at runtime via configuration."""

    def __init__(self, message: str, event_id: str | None = None):
        super().__init__(message)
        self.event_id = event_id


# The four fixed counterfactual arms a ticket may declare as its one delta.
DELTA_KINDS = frozenset(
    {"none", "generic_context", "selected_cards", "oracle_context"}
)


def _validate_arm_declaration(
    arm_id: str | None, delta: dict[str, Any] | None
) -> None:
    """Validate a ticket's declared arm before anything is recorded.

    A ticket declares exactly one delta: a single {"kind", "ref"} object.
    A list means the caller tried to carry more than one delta, which is
    rejected at creation so a rejected arm never writes a timeline event.
    """
    if arm_id is not None and not isinstance(arm_id, str):
        raise ValueError(f"arm_id must be a string; got {type(arm_id).__name__}")
    if delta is None:
        return
    if isinstance(delta, list):
        raise ValueError(
            "a replay ticket declares exactly one delta; got a list of "
            f"{len(delta)} deltas"
        )
    if not isinstance(delta, dict):
        raise ValueError(
            "delta must be a single {'kind', 'ref'} object; got "
            f"{type(delta).__name__}"
        )
    kind = delta.get("kind")
    if kind not in DELTA_KINDS:
        raise ValueError(
            f"unknown delta kind {kind!r}; expected one of {sorted(DELTA_KINDS)}"
        )
    ref = delta.get("ref")
    if ref is not None and not isinstance(ref, str):
        raise ValueError("delta ref must be a string naming the material, or null")


def prepare_replay(
    run_id: str,
    checkpoint_id: str,
    mode: str = "dry_run",
    approved: bool = False,
    arm_id: str | None = None,
    delta: dict[str, Any] | None = None,
) -> ReplayTicket:
    if mode not in MODES:
        raise ValueError(f"unknown replay mode {mode!r}; expected one of {MODES}")
    _validate_arm_declaration(arm_id, delta)
    if mode not in FREE_MODES:
        ensure_premium("replay_policies")

    state_doc = ckpt_engine.state_at_checkpoint(run_id, checkpoint_id)
    checkpoint = state_doc["checkpoint"]

    if not config.replay_enabled():
        disabled_event = event_engine.append_event(
            run_id,
            "replay_disabled",
            name="replay_disabled",
            payload={
                "actor": "operator",
                "checkpoint_id": checkpoint_id,
                "mode": mode,
                "approved": approved,
            },
        )
        raise ReplayDisabled(
            "Replay is disabled by the operator.",
            event_id=disabled_event["id"],
        )

    try:
        tool_plan, mock_results = build_tool_plan(run_id, mode, approved)
    except ReplayLimitExhausted as exc:
        limit_event = event_engine.append_event(
            run_id,
            "replay_limit_exhausted",
            name="replay_limit_exhausted",
            payload={
                "actor": "system",
                "reason": exc.reason,
                "checkpoint_id": checkpoint_id,
                "mode": mode,
            },
        )
        raise ReplayLimitExhausted(
            reason=exc.reason,
            event_id=limit_event["id"],
        ) from exc
    except Exception as exc:
        event_engine.append_event(
            run_id,
            "replay_failed",
            name="replay_failed",
            payload={
                "actor": "system",
                "exception": repr(exc),
                "message": str(exc),
                "checkpoint_id": checkpoint_id,
                "mode": mode,
            },
        )
        raise

    replay_event = event_engine.append_event(
        run_id,
        "log",
        name="replay_requested",
        payload={
            "actor": "replay",
            "checkpoint_id": checkpoint_id,
            "label": checkpoint.get("label"),
            "mode": mode,
            "approved": approved,
            "arm_id": arm_id,
            "delta": delta,
            "tool_plan": tool_plan,
        },
    )

    blocked = sorted(t for t, p in tool_plan.items() if p["action"] == "block")
    notes = "side-effecting tools are mocked unless explicitly allowed"
    if blocked:
        notes += f"; blocked (requires approval): {', '.join(blocked)}"

    return ReplayTicket(
        run_id=run_id,
        checkpoint_id=checkpoint_id,
        label=checkpoint.get("label"),
        mode=mode,
        state=state_doc["state"],
        status="ready",
        message=(
            "Replay ticket prepared. Pass this state to your registered resume "
            "handler (afr.hooks.register_resume_handler) or `afr replay --handler`."
        ),
        replay_event_id=replay_event["id"],
        extras={
            "tool_plan": tool_plan,
            "mock_results": mock_results,
            "policy_notes": notes,
            "arm_id": arm_id,
            "delta": delta,
        },
    )
