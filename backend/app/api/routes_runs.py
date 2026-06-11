"""Run lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.errors import not_found_to_404
from app.engine import checkpoints as ckpt_engine
from app.engine import runs as run_engine
from app.schemas import CheckpointIn, CheckpointOut, EndIn, RunCreate, RunOut

router = APIRouter(tags=["runs"])


@router.post("/runs", response_model=RunOut, status_code=201)
def create_run(body: RunCreate) -> dict:
    return run_engine.create_run(name=body.name, metadata=body.metadata)


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return run_engine.list_runs(status=status, limit=limit, offset=offset)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str) -> dict:
    with not_found_to_404():
        return run_engine.get_run(run_id)


@router.post("/runs/{run_id}/end", response_model=RunOut)
def end_run(run_id: str, body: EndIn | None = None) -> dict:
    with not_found_to_404():
        return run_engine.end_run(run_id, status=(body.status if body else "completed"))


@router.post("/runs/{run_id}/checkpoint", response_model=CheckpointOut, status_code=201)
def create_checkpoint(run_id: str, body: CheckpointIn | None = None) -> dict:
    body = body or CheckpointIn()
    with not_found_to_404():
        return ckpt_engine.create_checkpoint(run_id, label=body.label, state=body.state)


@router.get("/runs/{run_id}/checkpoints", response_model=list[CheckpointOut])
def list_checkpoints(run_id: str) -> list[dict]:
    with not_found_to_404():
        return ckpt_engine.list_checkpoints(run_id)
