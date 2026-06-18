"""Phase 01 SDK replay readiness controls.

Exercises the runtime kill switch, bounded execution, and durable failure
events end-to-end against the backend via an injected TestClient.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import afr
from afr.hooks import ReplayLimitExhausted


@pytest.fixture()
def sdk_client(api: TestClient) -> afr.AFRClient:
    return afr.AFRClient(http_client=api)


def _create_run_with_checkpoint(sdk_client: afr.AFRClient) -> tuple[str, dict]:
    with afr.start_run("replay-controls", client=sdk_client) as run:
        afr.log_state({"step": 1})
        ckpt = afr.checkpoint("before-replay")
    return run.run_id, ckpt


def test_replay_disabled_by_default_and_logs_event(monkeypatch, api, sdk_client):
    monkeypatch.delenv("AFR_REPLAY_ENABLED", raising=False)
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)

    result = afr.replay(run_id, ckpt["id"], mode="mock_tools", client=sdk_client)

    assert result["disabled"] is True
    assert result["reason"] == "replay disabled by operator"
    assert result["handler_invoked"] is False
    assert "event_id" in result
    assert result["event_id"] is not None

    events = sdk_client.list_events(run_id, event_type="replay_disabled")
    assert len(events) == 1
    assert events[0]["payload"]["actor"] == "replay"
    assert events[0]["payload"]["reason"] == "replay disabled by operator"


def test_replay_max_steps_logs_limit_event_and_raises(monkeypatch, sdk_client):
    monkeypatch.setenv("AFR_REPLAY_ENABLED", "true")
    monkeypatch.setenv("AFR_REPLAY_MAX_STEPS", "2")
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)

    @afr.register_resume_handler
    def greedy_handler(ctx: afr.ReplayContext):
        # Unrecorded tools are mocked in mock_tools mode, but every call_tool
        # invocation still counts against the operator step budget.
        ctx.call_tool("first", lambda: "ok")
        ctx.call_tool("second", lambda: "ok")
        ctx.call_tool("third", lambda: "ok")  # exceeds budget
        return "done"

    try:
        with pytest.raises(ReplayLimitExhausted) as exc_info:
            afr.replay(run_id, ckpt["id"], mode="mock_tools", client=sdk_client)
        assert exc_info.value.reason == "max_steps"
    finally:
        afr.clear_resume_handlers()

    events = sdk_client.list_events(run_id, event_type="replay_limit_exhausted")
    assert len(events) == 1
    assert events[0]["payload"]["actor"] == "replay"
    assert events[0]["payload"]["reason"] == "max_steps"


def test_replay_handler_failure_logs_failed_event_and_re_raises(monkeypatch, sdk_client):
    monkeypatch.setenv("AFR_REPLAY_ENABLED", "true")
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)

    @afr.register_resume_handler
    def failing_handler(_ctx: afr.ReplayContext):
        raise ValueError("handler blew up")

    try:
        with pytest.raises(ValueError, match="handler blew up"):
            afr.replay(run_id, ckpt["id"], mode="mock_tools", client=sdk_client)
    finally:
        afr.clear_resume_handlers()

    events = sdk_client.list_events(run_id, event_type="replay_failed")
    assert len(events) == 1
    assert events[0]["payload"]["actor"] == "replay"
    assert events[0]["payload"]["error_type"] == "ValueError"
    assert "handler blew up" in events[0]["payload"]["error"]
