"""Agent Flight Recorder — FastAPI application.

Routes are mounted twice: at the root (the canonical API documented in
docs/api.md) and under /api (schema-hidden copy used by the web UI and the
Vite dev proxy). If a built UI exists (ui/dist or $AFR_UI_DIST), it is served
as static files from "/" — the UI uses hash routing, so no SPA fallback
gymnastics are needed.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__, config
from app.api import build_router
from app.security import TokenAuthMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent Flight Recorder",
        description="AI agent observability, replay debugging, and checkpoint inspection for LLM apps",
        version=__version__,
    )

    # auth first, CORS second: add_middleware prepends, so CORS ends up
    # outermost and 401 responses still carry CORS headers
    app.add_middleware(TokenAuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "service": "agent-flight-recorder", "version": __version__}

    router = build_router()
    app.include_router(router)
    app.include_router(router, prefix="/api", include_in_schema=False)

    ui_dist = config.ui_dist_path()
    if ui_dist is not None:
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app


app = create_app()
