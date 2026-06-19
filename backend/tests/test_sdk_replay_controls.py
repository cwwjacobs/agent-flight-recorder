"""Phase 01 SDK replay readiness controls.

Exercises the runtime kill switch, bounded execution, and durable failure
events end-to-end against the backend via an injected TestClient.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import afr
from app import config as app_config
from afr import hooks as replay_hooks
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
    started = sdk_client.list_events(run_id, event_type="replay_started")
    assert len(started) == 1
    assert events[0]["payload"]["parent_event_id"] == started[0]["id"]
    assert events[0]["payload"]["correlation_id"]


def _ticket(run_id: str, checkpoint_id: str, status: object = "ready") -> dict:
    return {
        "run_id": run_id,
        "checkpoint_id": checkpoint_id,
        "label": "test",
        "mode": "mock_tools",
        "state": {"step": 1},
        "status": status,
        "message": "test ticket",
        "replay_event_id": "server-event-1",
        "tool_plan": {},
        "mock_results": {},
    }


def _assert_ticket_rejected(monkeypatch, sdk_client, ticket_factory, expected_status: str):
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)
    ticket = ticket_factory(run_id, ckpt["id"])
    called = False

    def handler(_ctx):
        nonlocal called
        called = True

    monkeypatch.setattr(sdk_client, "replay", lambda *_args, **_kwargs: ticket)
    result = afr.replay(
        run_id,
        ckpt["id"],
        mode="mock_tools",
        client=sdk_client,
        handler=handler,
    )

    assert result["handler_invoked"] is False
    assert result["rejected"] is True
    assert called is False
    events = sdk_client.list_events(run_id, event_type="replay_rejected")
    assert len(events) == 1
    assert events[0]["payload"]["actor"] == "replay"
    assert events[0]["payload"]["ticket_status"] == expected_status
    assert events[0]["payload"]["checkpoint_id"] == ckpt["id"]
    return result


def test_disabled_ticket_does_not_invoke_handler(monkeypatch, sdk_client):
    result = _assert_ticket_rejected(
        monkeypatch,
        sdk_client,
        lambda run_id, ckpt_id: _ticket(run_id, ckpt_id, "disabled"),
        "disabled",
    )
    assert result["disabled"] is True


def test_limit_exhausted_ticket_does_not_invoke_handler(monkeypatch, sdk_client):
    result = _assert_ticket_rejected(
        monkeypatch,
        sdk_client,
        lambda run_id, ckpt_id: _ticket(run_id, ckpt_id, "limit_exhausted"),
        "limit_exhausted",
    )
    assert result["limit_exhausted"] is True


@pytest.mark.parametrize(
    ("ticket_factory", "expected_status"),
    [
        (lambda run_id, ckpt_id: _ticket(run_id, ckpt_id, "unexpected"), "unexpected"),
        (
            lambda run_id, ckpt_id: {
                k: v for k, v in _ticket(run_id, ckpt_id).items() if k != "status"
            },
            "missing_or_malformed",
        ),
        (
            lambda run_id, ckpt_id: _ticket(run_id, ckpt_id, 123),
            "missing_or_malformed",
        ),
        (lambda _run_id, _ckpt_id: ["malformed", "ticket"], "missing_or_malformed"),
    ],
    ids=["unknown", "missing", "non-string", "malformed"],
)
def test_unknown_missing_or_malformed_status_does_not_invoke_handler(
    monkeypatch, sdk_client, ticket_factory, expected_status
):
    _assert_ticket_rejected(monkeypatch, sdk_client, ticket_factory, expected_status)


def test_ready_ticket_invokes_handler(monkeypatch, sdk_client):
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)
    monkeypatch.setattr(
        sdk_client,
        "replay",
        lambda *_args, **_kwargs: _ticket(run_id, ckpt["id"], "ready"),
    )
    called = False

    def handler(_ctx):
        nonlocal called
        called = True
        return "ok"

    result = afr.replay(
        run_id,
        ckpt["id"],
        mode="mock_tools",
        client=sdk_client,
        handler=handler,
    )

    assert called is True
    assert result["handler_invoked"] is True
    assert result["handler_result"] == "ok"


def test_replay_bound_defaults_are_finite(monkeypatch):
    for name in (
        "AFR_REPLAY_MAX_EVENTS",
        "AFR_REPLAY_MAX_OPERATIONS",
        "AFR_REPLAY_MAX_STEPS",
        "AFR_REPLAY_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    assert 0 < app_config.replay_max_events() < 1_000_000
    assert 0 < app_config.replay_timeout_seconds() < 3600
    assert 0 < replay_hooks._replay_max_steps() < 1_000_000
    assert 0 < replay_hooks._replay_timeout_seconds() < 3600


@pytest.mark.parametrize(
    ("name", "value", "reader"),
    [
        ("AFR_REPLAY_MAX_STEPS", "0", replay_hooks._replay_max_steps),
        ("AFR_REPLAY_MAX_STEPS", "invalid", replay_hooks._replay_max_steps),
        ("AFR_REPLAY_TIMEOUT_SECONDS", "0", replay_hooks._replay_timeout_seconds),
        (
            "AFR_REPLAY_TIMEOUT_SECONDS",
            "invalid",
            replay_hooks._replay_timeout_seconds,
        ),
    ],
)
def test_invalid_sdk_replay_bounds_fail_closed(monkeypatch, name, value, reader):
    monkeypatch.setenv(name, value)

    with pytest.raises(ReplayLimitExhausted):
        reader()


@pytest.mark.parametrize(
    ("name", "value", "reader"),
    [
        ("AFR_REPLAY_MAX_EVENTS", "0", app_config.replay_max_events),
        ("AFR_REPLAY_MAX_EVENTS", "invalid", app_config.replay_max_events),
        ("AFR_REPLAY_TIMEOUT_SECONDS", "0", app_config.replay_timeout_seconds),
        ("AFR_REPLAY_TIMEOUT_SECONDS", "invalid", app_config.replay_timeout_seconds),
    ],
)
def test_invalid_backend_replay_bounds_fail_closed(monkeypatch, name, value, reader):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        reader()


def test_replay_records_start_action_and_completion(monkeypatch, sdk_client):
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)
    sdk_client.append_event(
        run_id,
        "tool_call",
        name="lookup",
        payload={"tool": "lookup", "policy": "safe", "status": "ok", "result": {"ok": True}},
    )

    def handler(ctx):
        return ctx.call_tool("lookup", lambda: {"should_not": "run"})

    result = afr.replay(
        run_id,
        ckpt["id"],
        mode="mock_tools",
        client=sdk_client,
        handler=handler,
    )

    assert result["handler_invoked"] is True
    assert result["handler_result"] == {"ok": True}
    started = sdk_client.list_events(run_id, event_type="replay_started")
    actions = sdk_client.list_events(run_id, event_type="replay_action")
    completed = sdk_client.list_events(run_id, event_type="replay_completed")
    assert len(started) == len(actions) == len(completed) == 1
    assert actions[0]["payload"]["action"] == "mock"
    assert actions[0]["payload"]["status"] == "mocked"
    assert "result_digest" in actions[0]["payload"]
    assert completed[0]["payload"]["status"] == "completed"
    assert completed[0]["payload"]["parent_event_id"] == started[0]["id"]
    assert completed[0]["payload"]["correlation_id"]
