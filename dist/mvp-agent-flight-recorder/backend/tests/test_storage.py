"""Storage layer: append/read, ordering, indexes."""

from __future__ import annotations

from app.storage import connect, repo


def _mk_run(name: str = "r") -> dict:
    return repo.insert_run("run-1", name, "running", {"k": "v"}, "2026-01-01T00:00:00+00:00")


def test_insert_and_get_run():
    run = _mk_run("my-run")
    assert run["id"] == "run-1"
    assert run["name"] == "my-run"
    assert run["status"] == "running"
    assert run["metadata"] == {"k": "v"}
    assert run["events_count"] == 0


def test_events_append_and_read_in_order():
    _mk_run()
    for i in range(5):
        repo.insert_event(f"ev-{i}", "run-1", "log", f"e{i}", {"i": i}, f"2026-01-01T00:00:0{i}+00:00")

    events = repo.list_events("run-1")
    assert [e["name"] for e in events] == ["e0", "e1", "e2", "e3", "e4"]
    assert [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    assert events[2]["payload"] == {"i": 2}


def test_event_filters_and_pagination():
    _mk_run()
    for i in range(4):
        kind = "tool_call" if i % 2 == 0 else "log"
        repo.insert_event(f"ev-{i}", "run-1", kind, None, {}, "2026-01-01T00:00:00+00:00")

    tools = repo.list_events("run-1", event_type="tool_call")
    assert len(tools) == 2
    page = repo.list_events("run-1", limit=2, offset=2)
    assert len(page) == 2
    up_to = repo.list_events("run-1", up_to_seq=tools[0]["seq"])
    assert len(up_to) == 1


def test_required_indexes_exist():
    with connect() as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
    for expected in (
        "idx_events_run_id",
        "idx_events_created_at",
        "idx_events_event_type",
        "idx_events_run_created",
        "idx_events_run_type",
        "idx_checkpoints_run_id",
    ):
        assert expected in names, f"missing index {expected}"


def test_checkpoint_roundtrip_and_run_counts():
    _mk_run()
    event = repo.insert_event("ev-1", "run-1", "checkpoint", "cp", {}, "2026-01-01T00:00:01+00:00")
    repo.insert_checkpoint(
        "ck-1", "run-1", event["id"], event["seq"], "after-step", {"x": 1}, "2026-01-01T00:00:01+00:00"
    )

    checkpoint = repo.get_checkpoint("ck-1", include_state=True)
    assert checkpoint is not None
    assert checkpoint["state"] == {"x": 1}
    assert checkpoint["label"] == "after-step"

    run = repo.get_run("run-1")
    assert run is not None
    assert run["events_count"] == 1
    assert run["checkpoints_count"] == 1
