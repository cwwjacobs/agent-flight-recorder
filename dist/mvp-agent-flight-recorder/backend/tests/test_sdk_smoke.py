"""SDK smoke test: the whole SDK path against an in-process app.

starlette's TestClient is an httpx.Client, so we inject it straight into
AFRClient — full SDK + HTTP + engine + storage, no sockets.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import afr
from app.main import create_app


@pytest.fixture()
def sdk_client(api: TestClient) -> afr.AFRClient:
    return afr.AFRClient(http_client=api)


def test_sdk_full_flow(sdk_client):
    with afr.start_run("sdk-smoke", metadata={"suite": "tests"}, client=sdk_client) as run:
        afr.log("starting")
        afr.log_model(model="fake", input="hi", output="hello", duration_ms=3.2)
        afr.log_tool("calc", args={"a": 1}, result=2)
        afr.log_state({"step": 1})
        ckpt = afr.checkpoint("mid")
        afr.log_state({"step": 2}, mode="merge")

    run_doc = sdk_client.get_run(run.run_id)
    assert run_doc["status"] == "completed"

    events = sdk_client.list_events(run.run_id)
    types = [e["event_type"] for e in events]
    assert "model_call" in types and "tool_call" in types and "checkpoint" in types

    state = sdk_client.state_at(run.run_id, ckpt["id"])
    assert state["state"] == {"step": 1}


def test_sdk_records_failure_and_marks_run_failed(sdk_client):
    with pytest.raises(ValueError):
        with afr.start_run("sdk-fail", client=sdk_client) as run:
            raise ValueError("boom")

    run_doc = sdk_client.get_run(run.run_id)
    assert run_doc["status"] == "failed"
    errors = sdk_client.list_events(run.run_id, event_type="error")
    assert errors and "boom" in errors[0]["payload"]["message"]


def test_wrappers_record_calls_and_errors(sdk_client):
    @afr.record_tool_call
    def flaky(x: int) -> int:
        if x < 0:
            raise RuntimeError("negative")
        return x * 2

    @afr.record_model_call(model="fake-1")
    def model(prompt: str) -> str:
        return prompt.upper()

    with pytest.raises(RuntimeError):
        with afr.start_run("wrapped", client=sdk_client) as run:
            assert flaky(2) == 4
            assert model("hi") == "HI"
            flaky(-1)

    events = sdk_client.list_events(run.run_id)
    tool_events = [e for e in events if e["event_type"] == "tool_call"]
    assert len(tool_events) == 2
    assert tool_events[0]["payload"]["status"] == "ok"
    assert tool_events[0]["payload"]["result"] == 4
    assert tool_events[1]["payload"]["status"] == "error"
    model_events = [e for e in events if e["event_type"] == "model_call"]
    assert model_events[0]["payload"]["output"] == "HI"
    assert model_events[0]["payload"]["model"] == "fake-1"


def test_wrappers_are_noops_without_active_run():
    @afr.record_tool_call
    def add(a: int, b: int) -> int:
        return a + b

    assert add(1, 2) == 3  # no run open, no crash, nothing recorded


def test_sdk_replay_invokes_registered_handler(sdk_client):
    captured: dict = {}

    with afr.start_run("replayable", client=sdk_client) as run:
        afr.log_state({"counter": 41})
        ckpt = afr.checkpoint("before-finish")

    @afr.register_resume_handler
    def resume(ctx: afr.ReplayContext):
        captured["state"] = ctx.state
        captured["mode"] = ctx.mode
        return "resumed!"

    try:
        # dry_run: handler must NOT be invoked
        result = afr.replay(run.run_id, ckpt["id"], mode="dry_run", client=sdk_client)
        assert result["handler_invoked"] is False
        assert result["ticket"]["state"] == {"counter": 41}

        result = afr.replay(run.run_id, ckpt["id"], mode="mock_tools", client=sdk_client)
        assert result["handler_invoked"] is True
        assert result["handler_result"] == "resumed!"
        assert captured["state"] == {"counter": 41}
    finally:
        afr.clear_resume_handlers()
