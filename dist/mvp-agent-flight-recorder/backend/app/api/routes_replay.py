"""State-at-checkpoint and replay endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import not_found_to_404
from app.engine import checkpoints as ckpt_engine
from app.replay import prepare_replay
from app.schemas import ReplayIn, ReplayOut, StateAtOut

router = APIRouter(tags=["replay"])


@router.get("/runs/{run_id}/state-at/{checkpoint_id}", response_model=StateAtOut)
def state_at(run_id: str, checkpoint_id: str, reconstruct: bool = False) -> dict:
    with not_found_to_404():
        return ckpt_engine.state_at_checkpoint(run_id, checkpoint_id, reconstruct=reconstruct)


@router.post("/runs/{run_id}/replay", response_model=ReplayOut)
def replay(run_id: str, body: ReplayIn) -> dict:
    with not_found_to_404():
        ticket = prepare_replay(run_id, body.checkpoint_id, mode=body.mode)
    return ticket.to_dict()
