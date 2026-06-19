"""Replay safety policies: the decision matrix and the API behaviour."""

from __future__ import annotations

import pytest

from app.replay.policies import decide


@pytest.mark.parametrize(
    ("policy", "mode", "approved", "expected"),
    [
        # dry_run: nothing ever executes
        ("safe", "dry_run", False, "skip"),
        ("side_effecting", "dry_run", True, "skip"),
        # mock_tools: everything mocked
        ("safe", "mock_tools", False, "mock"),
        ("side_effecting", "mock_tools", False, "mock"),
        ("requires_approval", "mock_tools", True, "mock"),
        # allow_safe_tools: only safe runs
        ("safe", "allow_safe_tools", False, "allow"),
        ("side_effecting", "allow_safe_tools", False, "mock"),
        ("mock_by_default", "allow_safe_tools", False, "mock"),
        ("requires_approval", "allow_safe_tools", False, "mock"),
        # allow_side_effects: real execution, with guards
        ("safe", "allow_side_effects", False, "allow"),
        ("side_effecting", "allow_side_effects", False, "allow"),
        ("mock_by_default", "allow_side_effects", False, "mock"),
        ("requires_approval", "allow_side_effects", False, "block"),
        ("requires_approval", "allow_side_effects", True, "allow"),
        # unknown policy defaults to side_effecting
        ("nonsense", "allow_safe_tools", False, "mock"),
    ],
)
def test_decision_matrix(policy, mode, approved, expected):
    assert decide(policy, mode, approved) == expected


def _record_run_with_tools(api) -> tuple[str, str]:
    run_id = api.post("/runs", json={"name": "policy-run"}).json()["id"]
    api.post(
        f"/runs/{run_id}/events",
        json={
            "event_type": "tool_call",
            "name": "lookup",
            "payload": {"tool": "lookup", "policy": "safe", "result": {"hit": 1}, "status": "ok"},
        },
    )
    api.post(
        f"/runs/{run_id}/events",
        json={
            "event_type": "tool_call",
            "name": "send_email",
            "payload": {
                "tool": "send_email",
                "policy": "requires_approval",
                "result": "sent",
                "status": "ok",
            },
        },
    )
    api.post(
        f"/runs/{run_id}/events",
        json={
            "event_type": "tool_call",
            "name": "scrape",  # no policy recorded → side_effecting
            "payload": {"tool": "scrape", "result": ["page"], "status": "ok"},
        },
    )
    ckpt = api.post(f"/runs/{run_id}/checkpoint", json={"label": "cp"}).json()
    return run_id, ckpt["id"]


def test_safe_modes_work_without_experimental(api):
    run_id, ckpt_id = _record_run_with_tools(api)
    ticket = api.post(
        f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id, "mode": "mock_tools"}
    ).json()
    assert ticket["tool_plan"]["lookup"]["action"] == "mock"
    assert ticket["tool_plan"]["send_email"]["action"] == "mock"
    # mocked tools get record/replay results
    assert ticket["mock_results"]["lookup"] == {"hit": 1}
    assert ticket["mock_results"]["send_email"] == "sent"


def test_advanced_modes_are_gated(api):
    run_id, ckpt_id = _record_run_with_tools(api)
    r = api.post(
        f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id, "mode": "allow_side_effects"}
    )
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "experimental_feature_disabled"


def test_allow_side_effects_with_experimental(monkeypatch, api):
    monkeypatch.setenv("AFR_EXPERIMENTAL_FEATURES_ENABLED", "true")
    run_id, ckpt_id = _record_run_with_tools(api)

    # not approved: requires_approval tool is blocked
    ticket = api.post(
        f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id, "mode": "allow_side_effects"}
    ).json()
    assert ticket["tool_plan"]["lookup"]["action"] == "allow"
    assert ticket["tool_plan"]["scrape"]["action"] == "allow"
    assert ticket["tool_plan"]["send_email"]["action"] == "block"
    assert "send_email" in ticket["policy_notes"]

    # approved: unblocked
    ticket = api.post(
        f"/runs/{run_id}/replay",
        json={"checkpoint_id": ckpt_id, "mode": "allow_side_effects", "approved": True},
    ).json()
    assert ticket["tool_plan"]["send_email"]["action"] == "allow"


def test_allow_safe_tools_mocks_everything_else(monkeypatch, api):
    monkeypatch.setenv("AFR_EXPERIMENTAL_FEATURES_ENABLED", "true")
    run_id, ckpt_id = _record_run_with_tools(api)
    ticket = api.post(
        f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id, "mode": "allow_safe_tools"}
    ).json()
    assert ticket["tool_plan"]["lookup"]["action"] == "allow"
    assert ticket["tool_plan"]["scrape"]["action"] == "mock"
    assert ticket["tool_plan"]["send_email"]["action"] == "mock"


def test_invalid_mode_rejected(api):
    run_id, ckpt_id = _record_run_with_tools(api)
    r = api.post(f"/runs/{run_id}/replay", json={"checkpoint_id": ckpt_id, "mode": "yolo"})
    assert r.status_code == 422
