"""Forked replay (opt-in feature): branch a new run off any checkpoint.

The fork is a fresh run whose timeline starts with the parent's state as of
the checkpoint (seeded as a `state_snapshot`), plus lineage links in both
directions: child.parent_run_id / child.fork_checkpoint_id, and the parent
lists its forks.
"""

from __future__ import annotations

from app.engine.checkpoints import get_checkpoint, state_at_checkpoint
from app.engine.events import append_event
from app.engine.runs import get_run
from app.engine.util import new_id, utcnow
from app.storage import repo


def fork_run(run_id: str, checkpoint_id: str, name: str | None = None) -> dict:
    parent = get_run(run_id)
    checkpoint = get_checkpoint(checkpoint_id)
    state_doc = state_at_checkpoint(run_id, checkpoint_id)  # validates ownership
    label = checkpoint.get("label") or checkpoint_id[:8]

    fork = repo.insert_run(
        run_id=new_id(),
        name=name or f"{parent['name']} ⑂ {label}",
        status="running",
        metadata={**parent.get("metadata", {}), "forked_from_run": run_id},
        created_at=utcnow(),
        parent_run_id=run_id,
        fork_checkpoint_id=checkpoint_id,
        tags=list(parent.get("tags") or []),
    )

    append_event(
        fork["id"],
        "state_snapshot",
        name="forked_state",
        payload={
            "state": state_doc["state"],
            "mode": "replace",
            "forked_from_run": run_id,
            "forked_from_checkpoint": checkpoint_id,
        },
    )
    append_event(
        fork["id"],
        "log",
        name="forked",
        payload={
            "level": "info",
            "message": f"forked from run {run_id[:8]} @ checkpoint {label}",
            "data": {"parent_run_id": run_id, "checkpoint_id": checkpoint_id},
        },
    )
    append_event(
        run_id,
        "log",
        name="fork_created",
        payload={
            "level": "info",
            "message": f"fork {fork['id'][:8]} created from checkpoint {label}",
            "data": {"fork_run_id": fork["id"], "checkpoint_id": checkpoint_id},
        },
    )

    return get_run(fork["id"])


def list_forks(run_id: str) -> list[dict]:
    return repo.list_forks(run_id)
