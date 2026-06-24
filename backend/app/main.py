"""Agent Flight Recorder FastAPI application.

The canonical API is mounted at the root and mirrored under /api for adapter
compatibility. If AFR_UI_DIST points to a built static bundle, it can still be
served from "/", but the default runtime is backend/CLI-first.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__, config
from app.api import build_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent Flight Recorder",
        description="Local-first run recorder, replay-ticket helper, and regression-case source for tool-using agents",
        version=__version__,
    )

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
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="static")

    return app


app = create_app()
