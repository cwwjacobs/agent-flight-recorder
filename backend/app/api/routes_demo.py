"""Demo seeding (local/dev convenience).

Enabled by default because AFR is a local devtool; shared deployments can
turn it off with AFR_DEMO_SEED_ENABLED=false. When AFR_API_TOKEN is set the
endpoint also sits behind bearer auth like every other /demo route.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import config
from app.engine import demo as demo_engine

router = APIRouter(tags=["demo"])


@router.post("/demo/seed", status_code=201)
def seed_demo() -> dict:
    if not config.demo_seed_enabled():
        raise HTTPException(
            status_code=403,
            detail="demo seeding is disabled on this server (AFR_DEMO_SEED_ENABLED=false)",
        )
    return demo_engine.seed_demo_run()
