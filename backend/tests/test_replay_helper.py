"""ReplayContext.call_tool — the SDK side of the replay safety plan."""

from __future__ import annotations

import pytest

from afr import AFRClient, ReplayContext, ToolBlockedError
from afr.hooks import build_replay_context


def make_ctx(mode: str, tool_plan: dict, mock_results: dict | None = None) -> ReplayContext:
    return build_replay_context(
        {
            "run_id": "r1",
            "checkpoint_id": "c1",
            "label": "test",
            "mode": mode,
            "state": {},
            "tool_plan": tool_plan,
            "mock_results": mock_results or {},
        }
    )


def test_allow_executes_the_function():
    ctx = make_ctx("allow_safe_tools", {"lookup": {"policy": "safe", "action": "allow"}})
    calls: list[tuple] = []

    def lookup(q, limit=1):
        calls.append((q, limit))
        return ["hit"]

    assert ctx.call_tool("lookup", lookup, "query", limit=3) == ["hit"]
    assert calls == [("query", 3)]


def test_mock_returns_recorded_result_without_executing():
    ctx = make_ctx(
        "mock_tools",
        {"reserve": {"policy": "side_effecting", "action": "mock"}},
        mock_results={"reserve": {"reservation_id": "rsv-1"}},
    )

    def reserve(*a, **k):
        raise AssertionError("must not execute")

    assert ctx.call_tool("reserve", reserve) == {"reservation_id": "rsv-1"}


def test_mock_without_recorded_result_falls_back_to_default():
    ctx = make_ctx("mock_tools", {"reserve": {"policy": "side_effecting", "action": "mock"}})
    assert ctx.call_tool("reserve", lambda: None, default={"ok": False}) == {"ok": False}


def test_skip_returns_default_without_executing():
    ctx = make_ctx("dry_run", {"reserve": {"policy": "side_effecting", "action": "skip"}})

    def reserve():
        raise AssertionError("must not execute")

    assert ctx.call_tool("reserve", reserve, default="skipped") == "skipped"


def test_block_raises_a_clear_error():
    ctx = make_ctx(
        "allow_side_effects", {"charge": {"policy": "requires_approval", "action": "block"}}
    )
    with pytest.raises(ToolBlockedError, match="charge.*approval"):
        ctx.call_tool("charge", lambda: None)


def test_unplanned_tool_is_never_executed_by_accident():
    # free backend / unrecorded tool: no plan entry -> mock, not allow
    ctx = make_ctx("mock_tools", {})

    def surprise():
        raise AssertionError("must not execute")

    assert ctx.call_tool("surprise", surprise, default="mocked") == "mocked"


def test_client_sends_bearer_token(monkeypatch):
    client = AFRClient(token="abc123")
    try:
        assert client._http.headers["authorization"] == "Bearer abc123"
    finally:
        client.close()

    monkeypatch.setenv("AFR_API_TOKEN", "from-env")
    client = AFRClient()
    try:
        assert client._http.headers["authorization"] == "Bearer from-env"
    finally:
        client.close()

    monkeypatch.delenv("AFR_API_TOKEN")
    client = AFRClient()
    try:
        assert "authorization" not in client._http.headers
    finally:
        client.close()
