"""State-at-checkpoint and replay endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import not_found_to_404
from app.engine import checkpoints as ckpt_engine
from app.replay import prepare_replay
from app.replay.policies import ReplayLimitExhausted
from app.replay.service import ReplayDisabled
from app.schemas import ReplayIn, ReplayOut, StateAtOut

router = APIRouter(tags=["replay"])


def _disabled_out(run_id: str, body: ReplayIn, exc: ReplayDisabled) -> dict:
    return {
        "run_id": run_id,
        "checkpoint_id": body.checkpoint_id,
        "label": None,
        "mode": body.mode,
        "state": {},
        "status": "disabled",
        "message": str(exc),
        "replay_event_id": exc.event_id or "",
        "tool_plan": {},
        "mock_results": {},
        "policy_notes": None,
    }


def _limit_exhausted_out(run_id: str, body: ReplayIn, exc: ReplayLimitExhausted) -> dict:
    return {
        "run_id": run_id,
        "checkpoint_id": body.checkpoint_id,
        "label": None,
        "mode": body.mode,
        "state": {},
        "status": "limit_exhausted",
        "message": f"Replay limit exhausted: {exc.reason}.",
        "replay_event_id": exc.event_id or "",
        "tool_plan": {},
        "mock_results": {},
        "policy_notes": None,
    }


@router.get("/runs/{run_id}/state-at/{checkpoint_id}", response_model=StateAtOut)
def state_at(run_id: str, checkpoint_id: str, reconstruct: bool = False) -> dict:
    with not_found_to_404():
        return ckpt_engine.state_at_checkpoint(run_id, checkpoint_id, reconstruct=reconstruct)


@router.post("/runs/{run_id}/replay", response_model=ReplayOut)
def replay(run_id: str, body: ReplayIn) -> dict:
    try:
        with not_found_to_404():
            ticket = prepare_replay(
                run_id, body.checkpoint_id, mode=body.mode, approved=body.approved
            )
    except ReplayDisabled as exc:
        return _disabled_out(run_id, body, exc)
    except ReplayLimitExhausted as exc:
        return _limit_exhausted_out(run_id, body, exc)
    return ticket.to_dict()
