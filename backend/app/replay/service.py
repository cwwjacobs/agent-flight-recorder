"""Server-side replay preparation (see contract.py for the full contract).

The advanced (opt-in) path extends the base ticket with a per-tool safety plan
computed by policies.py — the safe-by-default matrix over recorded tool
policies — plus record/replay mock results (the last successful recorded result
for every tool the plan mocks). The always-on path is restricted to the
inherently safe modes (dry_run, mock_tools).
"""

from __future__ import annotations

from app import config
from app.engine import checkpoints as ckpt_engine
from app.engine import events as event_engine
from app.license import require_experimental
from app.replay.contract import ReplayTicket
from app.replay.policies import MODES, SAFE_MODES, ReplayLimitExhausted, build_tool_plan


class ReplayDisabled(Exception):
    """Raised when replay has been disabled at runtime via configuration."""

    def __init__(self, message: str, event_id: str | None = None):
        super().__init__(message)
        self.event_id = event_id


def prepare_replay(
    run_id: str,
    checkpoint_id: str,
    mode: str = "dry_run",
    approved: bool = False,
) -> ReplayTicket:
    if mode not in MODES:
        raise ValueError(f"unknown replay mode {mode!r}; expected one of {MODES}")
    if mode not in SAFE_MODES:
        require_experimental("replay_policies")

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
        },
    )
