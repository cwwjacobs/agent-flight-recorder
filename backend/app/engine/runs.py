"""Run lifecycle."""

from __future__ import annotations

from typing import Any

from app.engine.util import new_id, utcnow
from app.redaction import apply_redaction
from app.storage import repo


class RunNotFound(LookupError):
    pass


def create_run(name: str | None = None, metadata: dict[str, Any] | None = None) -> dict:
    run_id = new_id()
    created_at = utcnow()
    run_name = name or f"run-{created_at[:19]}"
    return repo.insert_run(run_id, run_name, "running", apply_redaction(metadata or {}), created_at)


def get_run(run_id: str) -> dict:
    run = repo.get_run(run_id)
    if run is None:
        raise RunNotFound(run_id)
    return run


def get_run_detail(run_id: str) -> dict:
    """Run plus its fork children (premium lineage view)."""
    run = get_run(run_id)
    run["forks"] = [
        {
            "id": f["id"],
            "name": f["name"],
            "status": f["status"],
            "fork_checkpoint_id": f.get("fork_checkpoint_id"),
            "created_at": f["created_at"],
        }
        for f in repo.list_forks(run_id)
    ]
    return run


def list_runs(
    status: str | None = None,
    tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    return repo.list_runs(status=status, tag=tag, limit=limit, offset=offset)


def update_run(
    run_id: str,
    name: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    get_run(run_id)
    if tags is not None:
        tags = sorted({t.strip() for t in tags if t.strip()})
    return repo.update_run_fields(run_id, name=name, tags=tags, notes=notes)  # type: ignore[return-value]


def end_run(run_id: str, status: str = "completed") -> dict:
    get_run(run_id)  # 404 if missing
    run = repo.set_run_status(run_id, status, utcnow())
    return run  # type: ignore[return-value]
