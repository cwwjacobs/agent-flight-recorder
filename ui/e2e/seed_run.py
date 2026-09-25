"""Seed a >10k-event run for the browser E2E journey.

Run with the repo venv python and PYTHONPATH pointing at backend/ (see
serve-e2e.sh). Writes the run/checkpoint ids as JSON to stdout so the
Playwright spec can address them.

Events are bulk-inserted in one SQLite transaction (mirroring what the
engine's append/checkpoint paths write) because the journey under test is
the UI's read/pagination/replay surface, not HTTP ingest throughput.
"""

from __future__ import annotations

import json

from app.storage import repo

LOG_EVENTS = 10_300
SNAPSHOT_EVERY = 500
MODEL_CALLS = 120
TOOL_CALLS = 40

TOOLS = [
    ("lookup_flights", "safe"),
    ("charge_card", "side_effecting"),
    ("email_user", "requires_approval"),
]

CHECKPOINT_AT_LOG = {4_000: "mid-run", 9_000: "late-run"}


def main() -> None:
    run = repo.insert_run(
        "e2e-journey-run",
        "e2e-10k",
        "running",
        {"seeded": "ui-e2e"},
        "2026-01-01T00:00:00+00:00",
    )
    run_id = run["id"]
    checkpoints: list[dict] = []
    total = 0

    def checkpoint_tx(conn, label: str, progress: int, created_at: str) -> None:
        event = repo.insert_event_tx(
            conn,
            event_id=f"e2e-ckpt-event-{label}",
            run_id=run_id,
            event_type="checkpoint",
            name=label,
            payload={"checkpoint_id": f"e2e-ckpt-{label}", "label": label},
            created_at=created_at,
        )
        repo.insert_checkpoint_tx(
            conn,
            checkpoint_id=f"e2e-ckpt-{label}",
            run_id=run_id,
            event_id=event["id"],
            event_seq=event["seq"],
            label=label,
            state={"progress": progress},
            created_at=created_at,
        )
        checkpoints.append(
            {"id": f"e2e-ckpt-{label}", "label": label, "event_seq": event["seq"]}
        )

    with repo.transaction(immediate=True) as conn:
        for i in range(LOG_EVENTS):
            created_at = f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00"
            repo.insert_event_tx(
                conn,
                event_id=f"e2e-log-{i}",
                run_id=run_id,
                event_type="log",
                name=f"tick-{i}",
                payload={"i": i},
                created_at=created_at,
            )
            total += 1
            if i % SNAPSHOT_EVERY == 0:
                repo.insert_event_tx(
                    conn,
                    event_id=f"e2e-snap-{i}",
                    run_id=run_id,
                    event_type="state_snapshot",
                    name=None,
                    payload={"state": {"progress": i}, "mode": "merge"},
                    created_at=created_at,
                )
                total += 1
            if i in CHECKPOINT_AT_LOG:
                checkpoint_tx(conn, CHECKPOINT_AT_LOG[i], i, created_at)
                total += 1
        for i in range(MODEL_CALLS):
            repo.insert_event_tx(
                conn,
                event_id=f"e2e-model-{i}",
                run_id=run_id,
                event_type="model_call",
                name=f"model-{i}",
                payload={"model": "fake-model", "i": i},
                created_at="2026-01-01T03:00:00+00:00",
            )
            total += 1
        for i in range(TOOL_CALLS):
            tool, policy = TOOLS[i % len(TOOLS)]
            repo.insert_event_tx(
                conn,
                event_id=f"e2e-tool-{i}",
                run_id=run_id,
                event_type="tool_call",
                name=tool,
                payload={
                    "tool": tool,
                    "policy": policy,
                    "status": "ok",
                    "result": {"call": i},
                },
                created_at="2026-01-01T04:00:00+00:00",
            )
            total += 1
        checkpoint_tx(conn, "final", LOG_EVENTS - (LOG_EVENTS % SNAPSHOT_EVERY), "2026-01-01T05:00:00+00:00")
        total += 1

    repo.set_run_status(run_id, "completed", "2026-01-01T06:00:00+00:00")
    print(
        json.dumps(
            {
                "run_id": run_id,
                "run_name": "e2e-10k",
                "total_events": total,
                "checkpoints": checkpoints,
                "tools": [tool for tool, _ in TOOLS],
                "last_progress": LOG_EVENTS - (LOG_EVENTS % SNAPSHOT_EVERY),
            }
        )
    )


if __name__ == "__main__":
    main()
