"""Full-stack journey over a >10k-event run, driven through the real API.

This is the non-browser spine of the KSL-03 journey (run → paginated
timeline → checkpoint → replay plan → export). The browser journey in
ui/e2e covers the same steps the UI can reach; export has no UI surface, so
here the export leg runs through the repo's actual export implementation
(``AFRClient.export_bundle`` → the CLI's ``afr export`` path) against the
same paginated endpoints.

Events are seeded in one bulk transaction so the test exercises pagination
and folding at scale instead of HTTP ingest throughput.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import afr
from app.storage import repo

LOG_EVENTS = 10_200
MODEL_CALLS = 200
TOOL_CALLS = 60
SNAPSHOT_EVERY = 500
SNAPSHOTS = LOG_EVENTS // SNAPSHOT_EVERY + 1  # i = 0, 500, ..., 10_000
TOTAL_EVENTS = LOG_EVENTS + MODEL_CALLS + TOOL_CALLS + SNAPSHOTS
LAST_PROGRESS = LOG_EVENTS - (LOG_EVENTS % SNAPSHOT_EVERY)  # 10_000

TOOLS = [
    ("lookup_flights", "safe"),
    ("charge_card", "side_effecting"),
    ("email_user", "requires_approval"),
]


@pytest.fixture()
def sdk_client(api: TestClient) -> afr.AFRClient:
    return afr.AFRClient(http_client=api)


def _seed_large_run() -> str:
    """Bulk-insert a deterministic >10k-event run; return its run_id."""
    run = repo.insert_run(
        "journey-large-run",
        "journey-10k",
        "running",
        {"seeded": True},
        "2026-01-01T00:00:00+00:00",
    )
    run_id = run["id"]
    with repo.transaction(immediate=True) as conn:
        for i in range(LOG_EVENTS):
            repo.insert_event_tx(
                conn,
                event_id=f"journey-log-{i}",
                run_id=run_id,
                event_type="log",
                name=f"tick-{i}",
                payload={"i": i},
                created_at=f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00",
            )
            if i % SNAPSHOT_EVERY == 0:
                repo.insert_event_tx(
                    conn,
                    event_id=f"journey-snap-{i}",
                    run_id=run_id,
                    event_type="state_snapshot",
                    name=None,
                    payload={"state": {"progress": i}, "mode": "merge"},
                    created_at=f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00",
                )
        for i in range(MODEL_CALLS):
            repo.insert_event_tx(
                conn,
                event_id=f"journey-model-{i}",
                run_id=run_id,
                event_type="model_call",
                name=f"model-{i}",
                payload={"model": "fake-model", "i": i},
                created_at="2026-01-01T01:00:00+00:00",
            )
        for i in range(TOOL_CALLS):
            tool, policy = TOOLS[i % len(TOOLS)]
            repo.insert_event_tx(
                conn,
                event_id=f"journey-tool-{i}",
                run_id=run_id,
                event_type="tool_call",
                name=tool,
                payload={
                    "tool": tool,
                    "policy": policy,
                    "status": "ok",
                    "result": {"call": i},
                },
                created_at="2026-01-01T02:00:00+00:00",
            )
    return run_id


def test_journey_run_paginated_timeline_checkpoint_replay_export(api, sdk_client):
    run_id = _seed_large_run()
    assert TOTAL_EVENTS > 10_000

    # -- run -----------------------------------------------------------------
    api.post(f"/runs/{run_id}/end", json={"status": "completed"})
    runs = api.get("/runs").json()
    seeded = next(r for r in runs if r["id"] == run_id)
    assert seeded["events_count"] == TOTAL_EVENTS
    assert seeded["status"] == "completed"

    # -- paginated timeline: every event exactly once, in seq order ----------
    paged: list[dict] = []
    offset = 0
    while True:
        page = api.get(f"/runs/{run_id}/events", params={"limit": 1000, "offset": offset}).json()
        paged.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)
    assert len(paged) == TOTAL_EVENTS
    assert [e["seq"] for e in paged] == list(range(1, TOTAL_EVENTS + 1))
    assert len({e["id"] for e in paged}) == TOTAL_EVENTS

    # The SDK's 10k-page walker (the same one export uses) must agree.
    walked = sdk_client.list_all_events(run_id)
    assert [e["id"] for e in walked] == [e["id"] for e in paged]

    # -- checkpoint: stored state and folded state agree at scale ------------
    ckpt = api.post(f"/runs/{run_id}/checkpoint", json={"label": "after-everything"}).json()
    stored = api.get(f"/runs/{run_id}/state-at/{ckpt['id']}").json()
    folded = api.get(
        f"/runs/{run_id}/state-at/{ckpt['id']}", params={"reconstruct": "true"}
    ).json()
    assert stored["source"] == "checkpoint_table"
    assert folded["source"] == "reconstructed"
    assert stored["state"] == folded["state"] == {"progress": LAST_PROGRESS}

    # The checkpoint is a timeline event too, and pagination still sees
    # everything after it landed.
    timeline_types = api.get(
        f"/runs/{run_id}/events", params={"event_type": "checkpoint"}
    ).json()
    assert [e["payload"]["checkpoint_id"] for e in timeline_types] == [ckpt["id"]]

    # -- replay plan: ready ticket, per-tool plan, no execution --------------
    ticket = api.post(
        f"/runs/{run_id}/replay",
        json={"checkpoint_id": ckpt["id"], "mode": "mock_tools"},
    ).json()
    assert ticket["status"] == "ready"
    assert ticket["state"] == {"progress": LAST_PROGRESS}
    assert set(ticket["tool_plan"]) == {tool for tool, _ in TOOLS}
    for tool, policy in TOOLS:
        assert ticket["tool_plan"][tool]["policy"] == policy
        assert ticket["tool_plan"][tool]["action"] == "mock"
    assert ticket["mock_results"]["lookup_flights"] == {"call": 57}

    requested = [
        e
        for e in sdk_client.list_all_events(run_id, event_type="log")
        if e["name"] == "replay_requested"
    ]
    assert len(requested) == 1
    assert requested[0]["payload"]["actor"] == "replay"
    # The server prepared a plan only — no handler lifecycle events exist.
    assert sdk_client.list_events(run_id, event_type="replay_started") == []

    # -- export: the real bundle path over the paginated endpoints -----------
    bundle = sdk_client.export_bundle(run_id)
    assert bundle["format"] == "afr.export.v1"
    assert bundle["run"]["id"] == run_id
    # +2 events: the checkpoint timeline event and the replay_requested log.
    assert len(bundle["events"]) == TOTAL_EVENTS + 2
    assert [e["seq"] for e in bundle["events"]] == list(range(1, TOTAL_EVENTS + 3))
    assert [c["id"] for c in bundle["checkpoints"]] == [ckpt["id"]]
