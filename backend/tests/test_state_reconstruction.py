"""State-at-checkpoint reconstruction semantics."""

from __future__ import annotations

import pytest

from app.engine import (
    append_event,
    create_checkpoint,
    create_run,
    fold_state,
    reconstruct_state,
    state_at_checkpoint,
)
from app.storage import repo


def test_fold_replace_and_merge():
    events = [
        {"event_type": "state_snapshot", "payload": {"state": {"a": 1, "nest": {"x": 1}}}},
        {"event_type": "log", "payload": {"message": "ignored"}},
        {"event_type": "state_snapshot", "payload": {"state": {"nest": {"y": 2}, "b": 2}, "mode": "merge"}},
    ]
    assert fold_state(events) == {"a": 1, "nest": {"x": 1, "y": 2}, "b": 2}

    # replace drops previous keys entirely
    events.append({"event_type": "state_snapshot", "payload": {"state": {"only": True}, "mode": "replace"}})
    assert fold_state(events) == {"only": True}


def test_state_at_checkpoint_reconstruction():
    run = create_run("recon")
    run_id = run["id"]

    append_event(run_id, "state_snapshot", payload={"state": {"step": 1, "items": ["a"]}})
    ckpt1 = create_checkpoint(run_id, label="first")

    append_event(run_id, "state_snapshot", payload={"state": {"step": 2}, "mode": "merge"})
    append_event(run_id, "state_snapshot", payload={"state": {"extra": True}, "mode": "merge"})
    ckpt2 = create_checkpoint(run_id, label="second")

    # state at the first checkpoint must not see later snapshots
    at1 = state_at_checkpoint(run_id, ckpt1["id"])
    assert at1["state"] == {"step": 1, "items": ["a"]}
    assert at1["source"] == "checkpoint_table"

    at2 = state_at_checkpoint(run_id, ckpt2["id"])
    assert at2["state"] == {"step": 2, "items": ["a"], "extra": True}

    # stored checkpoint state and event-fold reconstruction must agree
    recon1 = state_at_checkpoint(run_id, ckpt1["id"], reconstruct=True)
    assert recon1["source"] == "reconstructed"
    assert recon1["state"] == at1["state"]
    recon2 = state_at_checkpoint(run_id, ckpt2["id"], reconstruct=True)
    assert recon2["state"] == at2["state"]


def test_checkpoint_with_explicit_state():
    run = create_run("explicit")
    run_id = run["id"]
    append_event(run_id, "state_snapshot", payload={"state": {"ignored": "by explicit"}})

    ckpt = create_checkpoint(run_id, label="explicit", state={"authoritative": 1})
    at = state_at_checkpoint(run_id, ckpt["id"])
    assert at["state"] == {"authoritative": 1}

    # explicit state is also written to the timeline, so reconstruction agrees
    recon = reconstruct_state(run_id, up_to_seq=ckpt["event_seq"])
    assert recon == {"authoritative": 1}


def test_state_reconstruction_streams_across_multiple_pages():
    run = create_run("paged-reconstruction")
    run_id = run["id"]

    with repo.transaction() as conn:
        for i in range(2505):
            repo.insert_event_tx(
                conn,
                event_id=f"paged-{i}",
                run_id=run_id,
                event_type="state_snapshot",
                name=None,
                payload={"state": {"step": i}, "mode": "merge"},
                created_at="2026-01-01T00:00:00+00:00",
            )

    assert reconstruct_state(run_id) == {"step": 2504}


def test_checkpoint_creation_rolls_back_all_writes_on_failure(monkeypatch):
    run = create_run("atomic-checkpoint")
    run_id = run["id"]

    def fail_checkpoint_row(*_args, **_kwargs):
        raise RuntimeError("simulated checkpoint row failure")

    monkeypatch.setattr(repo, "insert_checkpoint_tx", fail_checkpoint_row)

    with pytest.raises(RuntimeError, match="simulated checkpoint row failure"):
        create_checkpoint(run_id, label="should-rollback", state={"step": 7})

    assert repo.list_events(run_id) == []
    assert repo.list_checkpoints(run_id, include_state=True) == []
