"""MCP stub: tool registry + HTTP dispatch."""

from __future__ import annotations

import pytest

from app.mcp import TOOLS


@pytest.fixture()
def premium(monkeypatch):
    monkeypatch.setenv("AFR_PREMIUM_ENABLED", "true")


EXPECTED_TOOLS = {
    "afr_list_runs",
    "afr_get_run",
    "afr_get_events",
    "afr_get_state_at_checkpoint",
    "afr_replay",
    "afr_fork_run",
    "afr_tag_run",
}


def test_registry_has_all_tools():
    assert set(TOOLS) == EXPECTED_TOOLS
    for tool in TOOLS.values():
        assert tool.description
        assert tool.input_schema["type"] == "object"


def test_mcp_endpoints_gated(api):
    assert api.get("/mcp/tools").status_code == 402
    assert api.post("/mcp/call", json={"tool": "afr_list_runs"}).status_code == 402


def test_mcp_list_and_call_roundtrip(premium, api):
    tools = api.get("/mcp/tools").json()
    assert tools["stub"] is True
    assert {t["name"] for t in tools["tools"]} == EXPECTED_TOOLS

    run_id = api.post("/runs", json={"name": "via-api"}).json()["id"]
    ckpt = api.post(f"/runs/{run_id}/checkpoint", json={"label": "cp"}).json()

    listed = api.post(
        "/mcp/call", json={"tool": "afr_list_runs", "arguments": {"limit": 5}}
    ).json()
    assert listed["ok"] is True
    assert any(r["id"] == run_id for r in listed["result"])

    tagged = api.post(
        "/mcp/call", json={"tool": "afr_tag_run", "arguments": {"run_id": run_id, "tags": ["mcp"]}}
    ).json()
    assert tagged["result"]["tags"] == ["mcp"]

    state = api.post(
        "/mcp/call",
        json={
            "tool": "afr_get_state_at_checkpoint",
            "arguments": {"run_id": run_id, "checkpoint_id": ckpt["id"]},
        },
    ).json()
    assert state["result"]["state"] == {}

    forked = api.post(
        "/mcp/call",
        json={"tool": "afr_fork_run", "arguments": {"run_id": run_id, "checkpoint_id": ckpt["id"]}},
    ).json()
    assert forked["result"]["parent_run_id"] == run_id


def test_mcp_errors(premium, api):
    assert api.post("/mcp/call", json={"tool": "nope"}).status_code == 404
    r = api.post(
        "/mcp/call", json={"tool": "afr_get_run", "arguments": {"bogus_arg": 1}}
    )
    assert r.status_code == 422
    assert api.post(
        "/mcp/call", json={"tool": "afr_get_run", "arguments": {"run_id": "missing"}}
    ).status_code == 404
