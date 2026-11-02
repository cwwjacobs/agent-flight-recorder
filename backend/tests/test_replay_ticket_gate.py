"""Replay ticket authorization gate (SDK side).

The backend ticket is an authorization boundary: the SDK may resolve and
invoke a resume handler only when ``ticket.status`` is exactly ``"ready"``.
These tests pin the two halves of that rule for non-ready tickets:

- no handler *resolution* — neither a ``module:function`` spec import nor a
  registered-handler lookup may happen behind the gate
- no handler *invocation* — including for tickets the real server produced
  (disabled / limit_exhausted), not only monkeypatched client responses

Complements test_sdk_replay_controls.py, which covers rejected statuses with
a stubbed client; this file drives genuine server-issued tickets through the
same gate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import afr
from afr import hooks as replay_hooks


@pytest.fixture()
def sdk_client(api: TestClient) -> afr.AFRClient:
    return afr.AFRClient(http_client=api)


def _create_run_with_checkpoint(sdk_client: afr.AFRClient) -> tuple[str, dict]:
    with afr.start_run("ticket-gate", client=sdk_client) as run:
        afr.log_state({"step": 1})
        ckpt = afr.checkpoint("gate")
    return run.run_id, ckpt


def _tracking_handler(calls: list[str]):
    def handler(_ctx):
        calls.append("invoked")
        return "should never run"

    return handler


@pytest.mark.parametrize(
    "status",
    ["disabled", "limit_exhausted", "unexpected", None],
    ids=["disabled", "limit_exhausted", "unknown", "missing"],
)
def test_non_ready_ticket_skips_handler_resolution_and_invocation(
    monkeypatch, sdk_client, status
):
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)
    ticket = {
        "run_id": run_id,
        "checkpoint_id": ckpt["id"],
        "label": "gate",
        "mode": "mock_tools",
        "state": {"step": 1},
        "message": "test ticket",
        "replay_event_id": "server-event-1",
        "tool_plan": {},
        "mock_results": {},
    }
    if status is not None:
        ticket["status"] = status
    monkeypatch.setattr(sdk_client, "replay", lambda *_a, **_k: ticket)

    calls: list[str] = []
    resolutions: list[str] = []
    monkeypatch.setattr(
        replay_hooks,
        "load_callable",
        lambda spec: resolutions.append(f"load:{spec}") or _tracking_handler(calls),
    )
    monkeypatch.setattr(
        replay_hooks,
        "get_resume_handler",
        lambda name="default": resolutions.append(f"lookup:{name}") or _tracking_handler(calls),
    )

    by_spec = afr.replay(
        run_id, ckpt["id"], mode="mock_tools", client=sdk_client,
        handler="some.module:resume",
    )
    by_registry = afr.replay(
        run_id, ckpt["id"], mode="mock_tools", client=sdk_client,
    )

    assert by_spec["handler_invoked"] is False
    assert by_registry["handler_invoked"] is False
    assert by_spec["rejected"] is True
    assert by_registry["rejected"] is True
    assert resolutions == []
    assert calls == []


def test_server_disabled_ticket_does_not_resolve_or_invoke_handler(
    monkeypatch, sdk_client
):
    """The server's own `disabled` ticket passes through the same SDK gate."""
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)
    # Backend replay kill-switch off; the SDK-side switch stays on so the
    # request really reaches the server and its ticket comes back.
    monkeypatch.setattr("app.config.replay_enabled", lambda: False)

    calls: list[str] = []
    monkeypatch.setattr(
        replay_hooks,
        "get_resume_handler",
        lambda name="default": _tracking_handler(calls),
    )

    result = afr.replay(run_id, ckpt["id"], mode="mock_tools", client=sdk_client)

    assert result["ticket"]["status"] == "disabled"
    assert result["disabled"] is True
    assert result["rejected"] is True
    assert result["handler_invoked"] is False
    assert calls == []
    # Server-side replay_disabled event plus the SDK's replay_rejected event.
    assert len(sdk_client.list_events(run_id, event_type="replay_disabled")) == 1
    rejected = sdk_client.list_events(run_id, event_type="replay_rejected")
    assert len(rejected) == 1
    assert rejected[0]["payload"]["ticket_status"] == "disabled"


def test_server_limit_exhausted_ticket_does_not_resolve_or_invoke_handler(
    monkeypatch, sdk_client
):
    """A genuine server limit_exhausted ticket never reaches a handler."""
    monkeypatch.setenv("AFR_REPLAY_MAX_EVENTS", "2")
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)
    for i in range(4):
        sdk_client.append_event(
            run_id,
            "tool_call",
            name=f"tool_{i}",
            payload={"tool": f"tool_{i}", "policy": "safe", "status": "ok", "result": i},
        )

    calls: list[str] = []
    monkeypatch.setattr(
        replay_hooks,
        "load_callable",
        lambda spec: _tracking_handler(calls),
    )

    result = afr.replay(
        run_id, ckpt["id"], mode="mock_tools", client=sdk_client,
        handler="some.module:resume",
    )

    assert result["ticket"]["status"] == "limit_exhausted"
    assert result["limit_exhausted"] is True
    assert result["rejected"] is True
    assert result["handler_invoked"] is False
    assert calls == []
    assert len(sdk_client.list_events(run_id, event_type="replay_limit_exhausted")) == 1
    rejected = sdk_client.list_events(run_id, event_type="replay_rejected")
    assert len(rejected) == 1
    assert rejected[0]["payload"]["ticket_status"] == "limit_exhausted"
    # Nothing about the rejected replay may look like an execution attempt.
    assert sdk_client.list_events(run_id, event_type="replay_started") == []
    assert sdk_client.list_events(run_id, event_type="replay_action") == []


def test_dry_run_ready_ticket_does_not_invoke_registered_handler(sdk_client):
    """Even a ready ticket must not invoke a handler in dry_run mode."""
    run_id, ckpt = _create_run_with_checkpoint(sdk_client)
    calls: list[str] = []
    afr.register_resume_handler(_tracking_handler(calls))
    try:
        result = afr.replay(run_id, ckpt["id"], mode="dry_run", client=sdk_client)
    finally:
        afr.clear_resume_handlers()

    assert result["ticket"]["status"] == "ready"
    assert result["handler_invoked"] is False
    assert calls == []
    assert sdk_client.list_events(run_id, event_type="replay_started") == []
