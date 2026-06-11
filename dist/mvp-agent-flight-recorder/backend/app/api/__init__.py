"""API routers."""

from fastapi import APIRouter

from app.api.routes_runs import router as runs_router
from app.api.routes_events import router as events_router
from app.api.routes_replay import router as replay_router


def build_router() -> APIRouter:
    router = APIRouter()
    router.include_router(runs_router)
    router.include_router(events_router)
    router.include_router(replay_router)
    return router
