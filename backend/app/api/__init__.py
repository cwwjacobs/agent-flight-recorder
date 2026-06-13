"""API routers."""

from fastapi import APIRouter, Depends

from app.api.routes_runs import router as runs_router
from app.api.routes_events import router as events_router
from app.api.routes_replay import router as replay_router
from app.api.routes_license import router as license_router
from app.api.routes_demo import router as demo_router
from app.auth import require_auth
from app.mcp.router import router as mcp_router


def build_router() -> APIRouter:
    # require_auth is a no-op unless AFR_API_TOKEN is set; when set it guards
    # every API route (both the root mount and the /api mirror in main.py).
    router = APIRouter(dependencies=[Depends(require_auth)])
    router.include_router(runs_router)
    router.include_router(events_router)
    router.include_router(replay_router)
    router.include_router(license_router)
    router.include_router(demo_router)
    router.include_router(mcp_router)
    return router
