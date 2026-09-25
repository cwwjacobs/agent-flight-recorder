"""Concurrent append/checkpoint/read coverage.

AFR's concurrency model is SQLite WAL mode plus short-lived per-call
connections (writes serialize on the single writer lock, ``timeout=30``
busy-waits; readers never block writers). These tests drive the engine from
threads and assert the persistence invariants:

- event sequences stay exact and contiguous (no lost or duplicated appends)
- checkpoint timeline events and checkpoint rows never dangle, even when
  checkpoint transactions fail under contention
- stored checkpoint state and event-fold reconstruction agree
- offset pagination and keyset streaming both deliver every event exactly once

Every repo read opens a fresh connection, so each assertion below is also a
post-restart read: no in-process state survives between calls.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.engine import (
    append_event,
    create_checkpoint,
    create_run,
    reconstruct_state,
    state_at_checkpoint,
)
from app.storage import connect, repo

WORKERS = 8


def _all_seqs(run_id: str) -> list[int]:
    return [e["seq"] for e in repo.iter_events(run_id, batch_size=64)]


def test_concurrent_appends_have_exact_contiguous_sequences():
    run_id = create_run("concurrent-appends")["id"]
    per_worker = 25

    def append_batch(worker: int) -> None:
        for i in range(per_worker):
            append_event(
                run_id,
                "log",
                name=f"w{worker}-e{i}",
                payload={"worker": worker, "i": i},
            )

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(append_batch, range(WORKERS)))

    events = list(repo.iter_events(run_id, batch_size=32))
    total = WORKERS * per_worker
    assert len(events) == total
    # seq is a global autoincrement; a run that only saw these appends must
    # hold exactly 1..total — anything else means a lost or duplicated write.
    assert sorted(e["seq"] for e in events) == list(range(1, total + 1))
    markers = {(e["payload"]["worker"], e["payload"]["i"]) for e in events}
    assert markers == {(w, i) for w in range(WORKERS) for i in range(per_worker)}


def test_concurrent_snapshots_and_checkpoints_keep_stored_and_folded_state_consistent():
    run_id = create_run("concurrent-state")["id"]
    writers = 4
    snapshots_per_writer = 40
    checkpoints_total = 12
    barrier = threading.Barrier(writers + 1)

    def write_snapshots(worker: int) -> None:
        barrier.wait()
        for i in range(snapshots_per_writer):
            append_event(
                run_id,
                "state_snapshot",
                payload={"state": {f"w{worker}": i}, "mode": "merge"},
            )

    def take_checkpoints() -> None:
        barrier.wait()
        for i in range(checkpoints_total):
            create_checkpoint(run_id, label=f"cp-{i}")

    with ThreadPoolExecutor(max_workers=writers + 1) as pool:
        futures = [pool.submit(write_snapshots, w) for w in range(writers)]
        futures.append(pool.submit(take_checkpoints))
        for future in futures:
            future.result()

    checkpoints = repo.list_checkpoints(run_id)
    assert len(checkpoints) == checkpoints_total

    # No dangling in either direction: every checkpoint event has its row and
    # every row has its timeline event (they share one writer transaction).
    checkpoint_events = repo.list_events(run_id, event_type="checkpoint", limit=10_000)
    row_event_ids = {c["event_id"] for c in checkpoints}
    event_checkpoint_ids = {e["payload"]["checkpoint_id"] for e in checkpoint_events}
    assert {c["id"] for c in checkpoints} == event_checkpoint_ids
    assert {e["id"] for e in checkpoint_events} == row_event_ids

    # Stored state must equal folding the events up to each checkpoint.
    for checkpoint in checkpoints:
        stored = state_at_checkpoint(run_id, checkpoint["id"])
        folded = state_at_checkpoint(run_id, checkpoint["id"], reconstruct=True)
        assert stored["state"] == folded["state"]

    # The final fold sees every writer's last snapshot — no lost updates.
    assert reconstruct_state(run_id) == {
        f"w{w}": snapshots_per_writer - 1 for w in range(writers)
    }


def test_checkpoint_failures_under_contention_leave_no_dangling_events(monkeypatch):
    run_id = create_run("concurrent-checkpoint-rollback")["id"]
    append_event(run_id, "state_snapshot", payload={"state": {"step": 1}})

    real_insert = repo.insert_checkpoint_tx
    attempts = 16
    barrier = threading.Barrier(attempts + 1)
    fail_lock = threading.Lock()
    failed: set[str] = set()

    def flaky_insert(conn, label=None, **kwargs):
        # Labels ending in "-fail" simulate a checkpoint-row write failure
        # after the timeline events were already staged in the transaction.
        if label and label.endswith("-fail"):
            with fail_lock:
                failed.add(label)
            raise RuntimeError("simulated checkpoint row failure")
        return real_insert(conn, label=label, **kwargs)

    monkeypatch.setattr(repo, "insert_checkpoint_tx", flaky_insert)

    def appender() -> None:
        barrier.wait()
        for i in range(attempts * 2):
            append_event(run_id, "log", name=f"late-{i}")

    def checkpoint_once(i: int) -> dict | None:
        barrier.wait()
        failing = i % 2 == 0
        label = f"cp-{i}-fail" if failing else f"cp-{i}"
        if failing:
            with pytest.raises(RuntimeError, match="simulated checkpoint row failure"):
                create_checkpoint(run_id, label=label)
            return None
        return create_checkpoint(run_id, label=label)

    with ThreadPoolExecutor(max_workers=attempts + 1) as pool:
        futures = [pool.submit(checkpoint_once, i) for i in range(attempts)]
        futures.append(pool.submit(appender))
        results = [f.result() for f in futures]

    assert len(failed) == attempts // 2

    checkpoint_events = repo.list_events(run_id, event_type="checkpoint", limit=10_000)
    rows = repo.list_checkpoints(run_id)
    # Atomicity: a rolled-back checkpoint leaves neither its timeline event
    # nor its row behind, in either direction.
    assert {c["id"] for c in rows} == {e["payload"]["checkpoint_id"] for e in checkpoint_events}
    assert {c["event_id"] for c in rows} == {e["id"] for e in checkpoint_events}
    assert len(rows) == attempts // 2
    # The successful checkpoints still carry consistent state.
    for checkpoint in results:
        if checkpoint is None:
            continue
        stored = state_at_checkpoint(run_id, checkpoint["id"])
        folded = state_at_checkpoint(run_id, checkpoint["id"], reconstruct=True)
        assert stored["state"] == folded["state"]


def test_pagination_is_loss_free_during_and_after_concurrent_appends():
    run_id = create_run("concurrent-pagination")["id"]
    pinned_total = 100
    for i in range(pinned_total):
        append_event(run_id, "log", name=f"pinned-{i}", payload={"i": i})
    pinned_max = max(_all_seqs(run_id))

    extra_total = 60
    stop = threading.Event()
    read_errors: list[AssertionError] = []

    def appender() -> None:
        for i in range(extra_total):
            append_event(run_id, "log", name=f"extra-{i}", payload={"i": pinned_total + i})
        stop.set()

    def pinned_reader() -> None:
        # A reader streaming a pinned snapshot (up_to_seq) must always see the
        # complete, ordered prefix — never a partial page cut by writers.
        while not stop.is_set():
            seqs = [
                e["seq"]
                for e in repo.iter_events(run_id, batch_size=7, up_to_seq=pinned_max)
            ]
            try:
                assert seqs == list(range(1, pinned_max + 1))
            except AssertionError as exc:
                read_errors.append(exc)
                return

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(appender) for _ in range(2)]
        futures += [pool.submit(pinned_reader) for _ in range(2)]
        for future in futures:
            future.result()

    assert not read_errors

    total = pinned_total + extra_total * 2
    # Offset pagination over the full range: every event exactly once.
    offset_events: list[dict] = []
    offset = 0
    page_size = 13
    while True:
        page = repo.list_events(run_id, limit=page_size, offset=offset)
        offset_events.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    # Keyset streaming over the same range must agree exactly.
    keyset_events = list(repo.iter_events(run_id, batch_size=11))

    assert len(offset_events) == total
    assert [e["seq"] for e in offset_events] == list(range(1, total + 1))
    assert [e["id"] for e in offset_events] == [e["id"] for e in keyset_events]

    # Sanity: the table really holds what both readers reported.
    with connect() as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM events WHERE run_id = ?", (run_id,)
        ).fetchone()
    assert count == total
