"""Phase 01 replay readiness controls."""

from __future__ import annotations

import pytest


def _create_run_and_checkpoint(api, extra_events=None):
    run_id = api.post("/runs", json={"name": "replay-control-run"}).json()["id"]
    for evt in extra_events or []:
        r = api.post(f"/runs/{run_id}/events", json=evt)
        assert r.status_code == 201
    # state isn't required for the controls under test, but a checkpoint is.
    ckpt = api.post(f"/runs/{run_id}/checkpoint", json={"label": "cp"}).json()
    return run_id, ckpt["id"]


def _last_event_of_type(api, run_id, event_type):
    events = api.get(f"/runs/{run_id}/events").json()
    for e in reversed(events):
        if e["event_type"] == event_type:
            return e
    return None


def test_replay_disabled_by_default(monkeypatch, api):
    """Without AFR_REPLAY_ENABLED the endpoint returns a clear disabled outcome
    and records a replay_disabled event."""
    monkeypatch.delenv("AFR_REPLAY_ENABLED", raising=False)
    run_id, ckpt_id = _create_run_and_checkpoint(api)

    r = api.post(f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id})
    assert r.status_code == 200
    ticket = r.json()
    assert ticket["status"] == "disabled"
    assert "disabled" in ticket["message"].lower()
    assert ticket["replay_event_id"]

    event = _last_event_of_type(api, run_id, "replay_disabled")
    assert event is not None
    assert event["payload"].get("actor") == "operator"
    assert event["payload"].get("checkpoint_id") == ckpt_id


def test_replay_enabled_returns_ready(monkeypatch, api):
    """With AFR_REPLAY_ENABLED=true the replay is prepared normally."""
    monkeypatch.setenv("AFR_REPLAY_ENABLED", "true")
    run_id, ckpt_id = _create_run_and_checkpoint(api)

    r = api.post(f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id})
    assert r.status_code == 200
    ticket = r.json()
    assert ticket["status"] == "ready"
    assert ticket["mode"] == "dry_run"
    assert ticket["replay_event_id"]

    requested = _last_event_of_type(api, run_id, "log")
    assert requested is not None
    assert requested["name"] == "replay_requested"
    assert requested["payload"].get("actor") == "replay"


def test_replay_max_events_limit_exceeded(monkeypatch, api):
    """Exceeding AFR_REPLAY_MAX_EVENTS returns limit_exhausted and records the
    bounded-replay failure event."""
    monkeypatch.setenv("AFR_REPLAY_ENABLED", "true")
    monkeypatch.setenv("AFR_REPLAY_MAX_EVENTS", "2")
    extra = [
        {
            "event_type": "tool_call",
            "name": f"tool_{i}",
            "payload": {
                "tool": f"tool_{i}",
                "policy": "safe",
                "status": "ok",
                "result": {"i": i},
            },
        }
        for i in range(4)
    ]
    run_id, ckpt_id = _create_run_and_checkpoint(api, extra_events=extra)

    r = api.post(f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id})
    assert r.status_code == 200
    ticket = r.json()
    assert ticket["status"] == "limit_exhausted"
    assert "limit" in ticket["message"].lower()
    assert ticket["replay_event_id"]

    event = _last_event_of_type(api, run_id, "replay_limit_exhausted")
    assert event is not None
    assert event["payload"].get("actor") == "system"
    assert "max_events" in event["payload"].get("reason", "")


def test_unexpected_failure_writes_replay_failed(monkeypatch, api):
    """Any unexpected exception during prepare_replay writes a replay_failed
    event before propagating."""

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.replay.service.build_tool_plan", _boom)
    run_id, ckpt_id = _create_run_and_checkpoint(api)

    with pytest.raises(RuntimeError, match="boom"):
        api.post(f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id})

    event = _last_event_of_type(api, run_id, "replay_failed")
    assert event is not None
    assert event["payload"].get("actor") == "system"
    assert "boom" in event["payload"].get("message", "")
    assert "RuntimeError" in event["payload"].get("exception", "")
