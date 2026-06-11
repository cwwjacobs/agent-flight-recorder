"""Server-side replay preparation (see contract.py for the full contract)."""

from __future__ import annotations

from app.engine import checkpoints as ckpt_engine
from app.engine import events as event_engine
from app.replay.contract import ReplayTicket


def prepare_replay(run_id: str, checkpoint_id: str, mode: str = "dry_run") -> ReplayTicket:
    state_doc = ckpt_engine.state_at_checkpoint(run_id, checkpoint_id)
    checkpoint = state_doc["checkpoint"]

    replay_event = event_engine.append_event(
        run_id,
        "log",
        name="replay_requested",
        payload={
            "checkpoint_id": checkpoint_id,
            "label": checkpoint.get("label"),
            "mode": mode,
        },
    )

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
    )
