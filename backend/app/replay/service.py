"""Server-side replay preparation (see contract.py for the full contract).

Premium extends the MVP ticket with a per-tool safety plan computed by
policies.py — the safe-by-default matrix over recorded tool policies — plus
record/replay mock results (the last successful recorded result for every
tool the plan mocks). Free mode is restricted to the inherently safe modes
(dry_run, mock_tools).
"""

from __future__ import annotations

from app.engine import checkpoints as ckpt_engine
from app.engine import events as event_engine
from app.license import ensure_premium
from app.replay.contract import ReplayTicket
from app.replay.policies import FREE_MODES, MODES, build_tool_plan


def prepare_replay(
    run_id: str,
    checkpoint_id: str,
    mode: str = "dry_run",
    approved: bool = False,
) -> ReplayTicket:
    if mode not in MODES:
        raise ValueError(f"unknown replay mode {mode!r}; expected one of {MODES}")
    if mode not in FREE_MODES:
        ensure_premium("replay_policies")

    state_doc = ckpt_engine.state_at_checkpoint(run_id, checkpoint_id)
    checkpoint = state_doc["checkpoint"]

    tool_plan, mock_results = build_tool_plan(run_id, mode, approved)

    replay_event = event_engine.append_event(
        run_id,
        "log",
        name="replay_requested",
        payload={
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
