"""Run lifecycle."""

from __future__ import annotations

from typing import Any

from app.engine.util import new_id, utcnow
from app.storage import repo


class RunNotFound(LookupError):
    pass


def create_run(name: str | None = None, metadata: dict[str, Any] | None = None) -> dict:
    run_id = new_id()
    created_at = utcnow()
    run_name = name or f"run-{created_at[:19]}"
    return repo.insert_run(run_id, run_name, "running", metadata or {}, created_at)


def get_run(run_id: str) -> dict:
    run = repo.get_run(run_id)
    if run is None:
        raise RunNotFound(run_id)
    return run


def list_runs(status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    return repo.list_runs(status=status, limit=limit, offset=offset)


def end_run(run_id: str, status: str = "completed") -> dict:
    get_run(run_id)  # 404 if missing
    run = repo.set_run_status(run_id, status, utcnow())
    return run  # type: ignore[return-value]
