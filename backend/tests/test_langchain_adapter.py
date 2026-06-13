"""LangChain adapter, driven with fake callback payloads.

langchain-core is intentionally not a test dependency: the adapter is
duck-typed, so we feed it the same shapes LangChain would (serialized dicts,
LLMResult-like objects) and assert on the recorded AFR events.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import afr
from afr.integrations import langchain as lc


@pytest.fixture()
def sdk_client(api: TestClient) -> afr.AFRClient:
    return afr.AFRClient(http_client=api)


def make_handler(**kwargs) -> lc.AFRCallbackHandler:
    return lc.AFRCallbackHandler(require_langchain=False, **kwargs)


def fake_llm_result(text: str, usage: dict | None = None):
    return SimpleNamespace(
        generations=[[SimpleNamespace(text=text)]],
        llm_output={"token_usage": usage} if usage else {},
    )


def test_constructor_requires_langchain_by_default():
    if lc.HAS_LANGCHAIN:
        pytest.skip("langchain-core installed; the guard is a no-op")
    with pytest.raises(ImportError, match=r"afr-sdk\[langchain\]"):
        lc.AFRCallbackHandler()


def test_llm_and_tool_callbacks_record_events(api, sdk_client):
    handler = make_handler(default_tool_policy="side_effecting")
    llm_id, tool_id = uuid4(), uuid4()

    with afr.start_run("lc-test", client=sdk_client) as run:
        handler.on_chain_start({"name": "checkout_chain"}, {"input": "refund order"}, run_id=uuid4())

        handler.on_llm_start(
            {"name": "fake-llm"}, ["plan the refund"], run_id=llm_id,
            invocation_params={"model_name": "fake-1"},
        )
        handler.on_llm_end(
            fake_llm_result("1) lookup 2) refund", {"prompt_tokens": 11, "total_tokens": 19}),
            run_id=llm_id,
        )

        handler.on_tool_start({"name": "lookup_order"}, "ord-1", run_id=tool_id)
        handler.on_tool_end({"order": "ord-1", "total": 42}, run_id=tool_id)

        handler.on_chain_end({"output": "done"}, run_id=uuid4())
        run_id = run.run_id

    events = api.get(f"/runs/{run_id}/events").json()
    by_type = {e["event_type"]: e for e in events}

    model = by_type["model_call"]
    assert model["payload"]["model"] == "fake-1"
    assert model["payload"]["provider"] == "langchain"
    assert model["payload"]["input"] == ["plan the refund"]
    assert model["payload"]["output"] == "1) lookup 2) refund"
    assert model["payload"]["usage"]["total_tokens"] == 19
    assert model["payload"]["duration_ms"] >= 0

    tool = by_type["tool_call"]
    assert tool["name"] == "lookup_order"
    assert tool["payload"]["policy"] == "side_effecting"
    assert tool["payload"]["result"] == {"order": "ord-1", "total": 42}


def test_tool_policy_overrides_and_capture_flags(api, sdk_client):
    handler = make_handler(
        capture_prompts=False,
        capture_outputs=False,
        tool_policies={"charge_customer": "requires_approval"},
    )
    llm_id, tool_id = uuid4(), uuid4()

    with afr.start_run("lc-flags", client=sdk_client) as run:
        handler.on_llm_start({"name": "llm"}, ["secret prompt"], run_id=llm_id)
        handler.on_llm_end(fake_llm_result("secret answer"), run_id=llm_id)
        handler.on_tool_start({"name": "charge_customer"}, "cus-1", run_id=tool_id)
        handler.on_tool_end("charged", run_id=tool_id)
        run_id = run.run_id

    events = api.get(f"/runs/{run_id}/events").json()
    model = next(e for e in events if e["event_type"] == "model_call")
    assert "input" not in model["payload"]
    assert "output" not in model["payload"]
    tool = next(e for e in events if e["event_type"] == "tool_call")
    assert tool["payload"]["policy"] == "requires_approval"
    assert "args" not in tool["payload"]
    assert "result" not in tool["payload"]


def test_errors_become_error_events(api, sdk_client):
    handler = make_handler()
    tool_id = uuid4()

    with afr.start_run("lc-errors", client=sdk_client) as run:
        handler.on_tool_start({"name": "reserve"}, "sku-1", run_id=tool_id)
        handler.on_tool_error(TimeoutError("inventory timeout"), run_id=tool_id)
        handler.on_chain_error(RuntimeError("chain exploded"), run_id=uuid4())
        run_id = run.run_id

    events = api.get(f"/runs/{run_id}/events").json()
    tool = next(e for e in events if e["event_type"] == "tool_call")
    assert tool["payload"]["status"] == "error"
    assert "TimeoutError" in tool["payload"]["error"]
    errors = [e for e in events if e["event_type"] == "error"]
    assert any("chain failed" in e["payload"]["message"] for e in errors)


def test_owned_run_lifecycle_without_active_context(api, sdk_client, monkeypatch):
    # no `with afr.start_run(...)`: the handler opens its own run and ends it
    # when the outermost chain finishes
    monkeypatch.setattr(
        lc,
        "start_run",
        lambda name, metadata=None: afr.start_run(name, metadata, client=sdk_client),
    )
    handler = make_handler(run_name="lc-owned", checkpoint_on_chain_end=True)

    handler.on_chain_start({"name": "outer"}, {"q": 1}, run_id=uuid4())
    handler.on_chain_end({"a": 2}, run_id=uuid4())

    runs = api.get("/runs").json()
    owned = next(r for r in runs if r["name"] == "lc-owned")
    assert owned["status"] == "completed"
    assert owned["checkpoints_count"] == 1
