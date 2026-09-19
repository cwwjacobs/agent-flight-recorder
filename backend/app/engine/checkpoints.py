"""Checkpoints.

A checkpoint is both:
  1. a row in the checkpoints table holding the authoritative state at that
     moment, and
  2. a `checkpoint` event on the timeline (so it appears in order with
     everything else).

If the caller supplies explicit state, we first append a `state_snapshot`
event carrying it — that keeps "fold the events" and "read the checkpoint
table" consistent with each other.
"""

from __future__ import annotations

from typing import Any

from app.engine.runs import get_run
from app.engine.state import fold_state, reconstruct_state
from app.engine.util import new_id, utcnow
from app.redaction import apply_redaction
from app.storage import repo


class CheckpointNotFound(LookupError):
    pass


def create_checkpoint(
    run_id: str,
    label: str | None = None,
    state: dict[str, Any] | None = None,
) -> dict:
    get_run(run_id)
    checkpoint_id = new_id()
    explicit_state = apply_redaction(state) if state is not None else None

    # The optional state event, checkpoint event, reconstructed state, and
    # checkpoint row share one SQLite writer transaction. A crash cannot leave
    # a visible checkpoint timeline event without its authoritative row.
    with repo.transaction(immediate=True) as conn:
        if explicit_state is not None:
            repo.insert_event_tx(
                conn,
                event_id=new_id(),
                run_id=run_id,
                event_type="state_snapshot",
                name="checkpoint_state",
                payload=apply_redaction(
                    {
                        "state": explicit_state,
                        "mode": "replace",
                        "checkpoint_id": checkpoint_id,
                    }
                ),
                created_at=utcnow(),
            )

        event = repo.insert_event_tx(
            conn,
            event_id=new_id(),
            run_id=run_id,
            event_type="checkpoint",
            name=label or "checkpoint",
            payload=apply_redaction({"checkpoint_id": checkpoint_id, "label": label}),
            created_at=utcnow(),
        )

        resolved_state = (
            explicit_state
            if explicit_state is not None
            else fold_state(
                repo.iter_events(
                    run_id,
                    event_type="state_snapshot",
                    batch_size=1000,
                    up_to_seq=event["seq"],
                    conn=conn,
                )
            )
        )

        return repo.insert_checkpoint_tx(
            conn,
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            event_id=event["id"],
            event_seq=event["seq"],
            label=label,
            state=resolved_state,
            created_at=utcnow(),
        )


def get_checkpoint(checkpoint_id: str, include_state: bool = False) -> dict:
    checkpoint = repo.get_checkpoint(checkpoint_id, include_state=include_state)
    if checkpoint is None:
        raise CheckpointNotFound(checkpoint_id)
    return checkpoint


def list_checkpoints(run_id: str) -> list[dict]:
    get_run(run_id)
    return repo.list_checkpoints(run_id)


def state_at_checkpoint(run_id: str, checkpoint_id: str, reconstruct: bool = False) -> dict:
    """State as of a checkpoint.

    Default reads the authoritative copy stored at checkpoint time; pass
    reconstruct=True to re-fold from events instead (debugging aid — the two
    must agree, and the test suite asserts they do).
    """
    get_run(run_id)
    checkpoint = get_checkpoint(checkpoint_id, include_state=True)
    if checkpoint["run_id"] != run_id:
        raise CheckpointNotFound(checkpoint_id)

    if reconstruct:
        state = reconstruct_state(run_id, up_to_seq=checkpoint["event_seq"])
        source = "reconstructed"
    else:
        state = checkpoint["state"]
        source = "checkpoint_table"

    return {
        "run_id": run_id,
        "checkpoint": {k: v for k, v in checkpoint.items() if k != "state"},
        "state": state,
        "source": source,
    }
