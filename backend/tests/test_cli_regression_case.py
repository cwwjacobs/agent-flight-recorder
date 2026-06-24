"""Focused tests for the CLI regression-case generator.

These tests use a fake client instead of TestClient so they do not exercise the
current Starlette/httpx2 blocker.
"""

from __future__ import annotations

import json

import afr_cli.main as cli_main


RUN_ID = "12345678-1234-4abc-9def-123456789abc"
CHECKPOINT_ID = "abcdef12-3456-4abc-9def-abcdef123456"


RUN = {
    "id": RUN_ID,
    "name": "checkout-agent",
    "status": "completed",
    "created_at": "2026-06-24T00:00:00+00:00",
    "ended_at": "2026-06-24T00:01:00+00:00",
    "metadata": {"suite": "cli-regression"},
}

CHECKPOINT = {
    "id": CHECKPOINT_ID,
    "label": "before-payment",
    "event_seq": 3,
    "created_at": "2026-06-24T00:00:30+00:00",
}

EVENTS = [
    {"seq": 1, "event_type": "log", "name": "start", "payload": {}},
    {"seq": 2, "event_type": "tool_call", "name": "lookup", "payload": {}},
    {"seq": 3, "event_type": "checkpoint", "name": "before-payment", "payload": {}},
]


class FakeClient:
    def __init__(self) -> None:
        self.replay_calls: list[tuple[str, str, str]] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def list_runs(self, **_kwargs: object) -> list[dict]:
        return [RUN]

    def list_checkpoints(self, run_id: str) -> list[dict]:
        assert run_id == RUN_ID
        return [CHECKPOINT]

    def export_bundle(self, run_id: str) -> dict:
        assert run_id == RUN_ID
        return {
            "format": "afr.export.v1",
            "run": RUN,
            "events": EVENTS,
            "checkpoints": [CHECKPOINT],
        }

    def state_at(self, run_id: str, checkpoint_id: str, reconstruct: bool = False) -> dict:
        assert run_id == RUN_ID
        assert checkpoint_id == CHECKPOINT_ID
        assert reconstruct is True
        return {
            "checkpoint": CHECKPOINT,
            "state": {"cart_id": "cart-1", "step": "before-payment"},
        }

    def replay(self, run_id: str, checkpoint_id: str, mode: str = "dry_run") -> dict:
        self.replay_calls.append((run_id, checkpoint_id, mode))
        return {
            "run_id": run_id,
            "checkpoint_id": checkpoint_id,
            "label": "before-payment",
            "mode": mode,
            "status": "ready",
            "message": "Replay ticket prepared.",
            "replay_event_id": "replay-event-1",
        }


def test_regression_case_writes_required_files_without_replay(
    tmp_path, monkeypatch, capsys
) -> None:
    fake = FakeClient()
    monkeypatch.delenv("AFR_REPLAY_ENABLED", raising=False)
    monkeypatch.setattr(cli_main, "make_client", lambda _args: fake)

    out_dir = tmp_path / "case"
    cli_main.main(
        ["regression-case", RUN_ID[:8], "--from", CHECKPOINT_ID[:8], "-o", str(out_dir)]
    )

    out = capsys.readouterr().out
    assert "wrote regression case template" in out
    assert fake.replay_calls == []

    case = json.loads((out_dir / "case.json").read_text())
    assert case["format"] == "afr.regression_case.v1"
    assert case["run"]["metadata"] == {"suite": "cli-regression"}
    assert case["checkpoint"]["id"] == CHECKPOINT_ID
    assert case["expected_reconstructed_state"]["state"] == {
        "cart_id": "cart-1",
        "step": "before-payment",
    }
    assert case["event_counts"] == {
        "total": 3,
        "by_type": {"checkpoint": 1, "log": 1, "tool_call": 1},
        "checkpoints": 1,
    }
    assert case["source_export_summary"] == {
        "format": "afr.export.v1",
        "run_id": RUN_ID,
        "run_status": "completed",
        "events": 3,
        "checkpoints": 1,
    }
    assert case["replay_ticket_reference"]["attempted"] is False
    assert case["replay_ticket_reference"]["generated"] is False

    test_template = (out_dir / "test_regression_12345678.py").read_text()
    assert "pytest.skip" in test_template
    assert "TODO: import your agent/resume function" in test_template
    assert "does not execute your agent" in test_template

    readme = (out_dir / "README.md").read_text()
    assert "What Remains User-Supplied" in readme
    assert "does not claim JSONL export support" in readme


def test_regression_case_includes_dry_run_ticket_when_replay_enabled(
    tmp_path, monkeypatch, capsys
) -> None:
    fake = FakeClient()
    monkeypatch.setenv("AFR_REPLAY_ENABLED", "true")
    monkeypatch.setattr(cli_main, "make_client", lambda _args: fake)

    out_dir = tmp_path / "case"
    cli_main.main(
        [
            "--json",
            "regression-case",
            RUN_ID[:8],
            "--from",
            CHECKPOINT_ID[:8],
            "-o",
            str(out_dir),
        ]
    )

    summary = json.loads(capsys.readouterr().out)
    assert summary["replay_ticket_generated"] is True
    assert fake.replay_calls == [(RUN_ID, CHECKPOINT_ID, "dry_run")]

    case = json.loads((out_dir / "case.json").read_text())
    assert case["replay_ticket_reference"] == {
        "attempted": True,
        "generated": True,
        "run_id": RUN_ID,
        "checkpoint_id": CHECKPOINT_ID,
        "label": "before-payment",
        "mode": "dry_run",
        "status": "ready",
        "replay_event_id": "replay-event-1",
        "message": "Replay ticket prepared.",
    }
