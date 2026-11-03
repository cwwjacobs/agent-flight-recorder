"""Step 2 arm-runner tests for the counterfactual replay harness.

The handler under test lives in examples/counterfactual_replay/ (an
importable example module, like examples/toy_agent/replay_handler.py).
The model seam (arm_handler.call_model) is monkeypatched in every test
— the suite never calls a real API. All delta materials used here are
test fixtures in tmp_path, labeled as such; no demo content is seeded.

Fixture-model convention: the fake model reads its prompt and, ONLY if
the arm's material carried a charge directive line
("idempotency_key: ord-..."), states that directive in its output —
simulating a model that uses the context it was given. The bare and
generic fixtures carry no directive, so their arms proceed with a
fresh charge attempt, exactly what the counterfactual is measuring.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import afr
from afr.hooks import ToolBlockedError, build_replay_context

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.counterfactual_replay import arm_handler  # noqa: E402
from examples.counterfactual_replay import run_arms  # noqa: E402

_DIRECTIVE_IN_PROMPT = re.compile(r"idempotency_key:\s*(ord-[\w\-]+)")


def _fake_model(prompt: str) -> dict:
    match = _DIRECTIVE_IN_PROMPT.search(prompt)
    if match:
        decision = f"Retry the charge with the recorded key.\nidempotency_key: {match.group(1)}"
    else:
        decision = "Proceed with a fresh charge attempt for the order."
    return {
        "model": "fixture-llm-1",
        "provider": "monkeypatched-seam",
        "output": f"Continue the checkout.\n{decision}",
        "status": "ok",
    }


@pytest.fixture()
def sdk_client(api: TestClient) -> afr.AFRClient:
    return afr.AFRClient(http_client=api)


@pytest.fixture()
def demo_fork(api: TestClient) -> tuple[str, str]:
    """Seed the demo incident; return (run_id, safe checkpoint id)."""
    doc = api.post("/demo/seed").json()
    return doc["run"]["id"], doc["checkpoints"]["safe"]["id"]


@pytest.fixture()
def materials(tmp_path: Path, monkeypatch) -> Path:
    """Fixture delta materials — test data, not demo content."""
    (tmp_path / "generic.txt").write_text(
        "Checkout guidance: verify inventory before charging, keep the "
        "customer informed, and confirm the order once payment settles. "
        "Standard payment retries use exponential backoff.",
        encoding="utf-8",
    )
    (tmp_path / "cards.json").write_text(
        '[{"title": "Payment timeout recovery", "body": "When a charge '
        "times out, the charge state is unknown. Retry with the recorded "
        "idempotency_key: ord-20917 to resolve the original attempt "
        'instead of charging again."}]',
        encoding="utf-8",
    )
    (tmp_path / "oracle.txt").write_text(
        "Known-correct resolution: the original charge attempt used "
        "idempotency_key: ord-20917. Retry the charge with that key; "
        "the gateway resolves the original attempt, which succeeded.",
        encoding="utf-8",
    )
    monkeypatch.setenv("AFR_ARM_MATERIALS_DIR", str(tmp_path))
    return tmp_path


def _arm_events(sdk_client: afr.AFRClient, run_id: str, event_type: str, correlation_id: str):
    return [
        e
        for e in sdk_client.list_events(run_id, event_type=event_type)
        if e["payload"].get("correlation_id") == correlation_id
    ]


# ---------------------------------------------------------------------------
# (1) THE BRIEF'S CHECK — the bare arm reproduces the recorded failure
# ---------------------------------------------------------------------------


def test_bare_arm_reproduces_the_recorded_failure(monkeypatch, demo_fork, sdk_client):
    monkeypatch.setattr(arm_handler, "call_model", _fake_model)
    run_id, ckpt_id = demo_fork

    result = afr.replay(
        run_id,
        ckpt_id,
        mode="mock_tools",
        client=sdk_client,
        handler=arm_handler.resume_arm,
        arm_id="bare",
        delta={"kind": "none", "ref": None},
    )

    assert result["handler_invoked"] is True
    summary = result["handler_result"]
    # The recorded failure was a payment timeout with the charge state
    # unknown and no confirmation; the bare arm lands in the same place.
    assert summary["outcome"] == "charge_timeout_unresolved"
    assert summary["confirmed"] is False
    assert summary["charge_status"] == "timeout_unresolved"

    correlation_id = result["ticket"]["replay_event_id"]
    outcomes = [
        e
        for e in _arm_events(sdk_client, run_id, "log", correlation_id)
        if e["payload"].get("arm_outcome") is True
    ]
    assert len(outcomes) == 1
    assert outcomes[0]["payload"]["outcome"] == "charge_timeout_unresolved"
    assert outcomes[0]["payload"]["confirmed"] is False


# ---------------------------------------------------------------------------
# (2) four arms, four correlation ids, no cross-talk
# ---------------------------------------------------------------------------


def test_four_arms_correlate_to_their_own_tickets(monkeypatch, demo_fork, materials, sdk_client):
    monkeypatch.setattr(arm_handler, "call_model", _fake_model)
    run_id, ckpt_id = demo_fork

    arms = [
        ("bare", {"kind": "none", "ref": None}),
        ("generic", {"kind": "generic_context", "ref": "generic.txt"}),
        ("selected", {"kind": "selected_cards", "ref": "cards.json"}),
        ("oracle", {"kind": "oracle_context", "ref": "oracle.txt"}),
    ]
    results = {}
    for arm_id, delta in arms:
        results[arm_id] = afr.replay(
            run_id,
            ckpt_id,
            mode="mock_tools",
            client=sdk_client,
            handler=arm_handler.resume_arm,
            arm_id=arm_id,
            delta=delta,
        )

    correlation_ids = {
        arm_id: r["ticket"]["replay_event_id"] for arm_id, r in results.items()
    }
    assert len(set(correlation_ids.values())) == 4

    # Each arm's declared delta is on its own replay_requested event.
    requested = [
        e
        for e in sdk_client.list_events(run_id, event_type="log")
        if e["name"] == "replay_requested" and e["payload"].get("arm_id")
    ]
    assert len(requested) == 4
    by_arm = {e["payload"]["arm_id"]: e for e in requested}
    for arm_id, delta in arms:
        assert by_arm[arm_id]["id"] == correlation_ids[arm_id]
        assert by_arm[arm_id]["payload"]["delta"] == delta

    # No cross-talk: each arm's model_call + outcome events carry only
    # its own correlation id, and the delta changes the outcome exactly
    # where the material carries the directive.
    expected_outcome = {
        "bare": "charge_timeout_unresolved",
        "generic": "charge_timeout_unresolved",
        "selected": "order_confirmed",
        "oracle": "order_confirmed",
    }
    for arm_id, _delta in arms:
        cid = correlation_ids[arm_id]
        model_calls = _arm_events(sdk_client, run_id, "model_call", cid)
        assert len(model_calls) == 1
        assert model_calls[0]["payload"]["arm_id"] == arm_id
        outcomes = [
            e
            for e in _arm_events(sdk_client, run_id, "log", cid)
            if e["payload"].get("arm_outcome") is True
        ]
        assert len(outcomes) == 1
        assert outcomes[0]["payload"]["arm_id"] == arm_id
        assert outcomes[0]["payload"]["outcome"] == expected_outcome[arm_id]
        assert results[arm_id]["handler_result"]["outcome"] == expected_outcome[arm_id]


# ---------------------------------------------------------------------------
# (3) side-effect enforcement inside a live arm
# ---------------------------------------------------------------------------


def test_mock_tools_arm_never_executes_real_tools(
    monkeypatch, demo_fork, materials, sdk_client, tmp_path
):
    monkeypatch.setattr(arm_handler, "call_model", _fake_model)
    marker = tmp_path / "live-tool-executed"

    def spy_charge(*args, **kwargs):
        marker.write_text("charge_customer really executed")
        return {"status": "succeeded"}

    monkeypatch.setattr(arm_handler, "charge_customer_live", spy_charge)
    run_id, ckpt_id = demo_fork

    result = afr.replay(
        run_id,
        ckpt_id,
        mode="mock_tools",
        client=sdk_client,
        handler=arm_handler.resume_arm,
        arm_id="bare",
        delta={"kind": "none", "ref": None},
    )

    assert result["handler_invoked"] is True
    # The real tool function never ran; the charge resolved to the
    # handler-supplied gateway stub default (the bare arm's fresh
    # attempt -> the stub's timeout outcome).
    assert not marker.exists()
    assert result["handler_result"]["charge_status"] == "timeout_unresolved"
    actions = sdk_client.list_events(run_id, event_type="replay_action")
    charge_actions = [a for a in actions if a["payload"]["tool"] == "charge_customer"]
    assert charge_actions
    assert {a["payload"]["action"] for a in charge_actions} == {"mock"}


def test_gated_mode_blocked_tool_raises_through_call_tool(monkeypatch):
    monkeypatch.setattr(arm_handler, "call_model", _fake_model)
    emitted: list[tuple[str, dict]] = []

    ticket = {
        "run_id": "run-gated",
        "checkpoint_id": "ckpt-gated",
        "label": "safe-before-side-effect",
        "mode": "allow_side_effects",
        "state": {
            "order": {
                "order_id": "ord-20917",
                "customer": "cus-48213",
                "items": [{"sku": "SKU-ORCHID-01", "qty": 1, "unit_price_usd": 129.0}],
                "total_usd": 129.0,
            },
            "step": "reserved",
            "reservation": {"id": "rsv-7841", "expires_in_s": 900},
        },
        "status": "ready",
        "replay_event_id": "evt-gated",
        "tool_plan": {
            "check_inventory": {"policy": "safe", "action": "mock"},
            "reserve_inventory": {"policy": "side_effecting", "action": "mock"},
            "charge_customer": {"policy": "requires_approval", "action": "block"},
        },
        "mock_results": {
            "check_inventory": {"sku": "SKU-ORCHID-01", "available": 7},
            "reserve_inventory": {"reservation_id": "rsv-7841", "expires_in_s": 900},
        },
        "arm_id": "bare",
        "delta": {"kind": "none", "ref": None},
    }
    ctx = build_replay_context(
        ticket,
        correlation_id="evt-gated",
        event_sink=lambda event_type, payload: emitted.append((event_type, payload)),
    )

    with pytest.raises(ToolBlockedError):
        arm_handler.resume_arm(ctx)

    # The arm got as far as emitting its model call before the plan
    # blocked the charge — the block, not a silent skip, is the result.
    assert emitted[0][0] == "model_call"
    actions = [p for t, p in emitted if t == "replay_action"]
    assert actions[-1]["tool"] == "charge_customer"
    assert actions[-1]["status"] == "blocked"


# ---------------------------------------------------------------------------
# (4) trace completeness — the events Step 3 will grade are in the trace
# ---------------------------------------------------------------------------


def test_arm_trace_carries_model_call_and_outcome_events(
    monkeypatch, demo_fork, materials, sdk_client
):
    monkeypatch.setattr(arm_handler, "call_model", _fake_model)
    run_id, ckpt_id = demo_fork

    result = afr.replay(
        run_id,
        ckpt_id,
        mode="mock_tools",
        client=sdk_client,
        handler=arm_handler.resume_arm,
        arm_id="selected",
        delta={"kind": "selected_cards", "ref": "cards.json"},
    )
    correlation_id = result["ticket"]["replay_event_id"]

    model_calls = _arm_events(sdk_client, run_id, "model_call", correlation_id)
    assert len(model_calls) == 1
    payload = model_calls[0]["payload"]
    # The recorded model_call shape (mirrors the demo incident's own
    # recorded call): substance, not just a digest.
    assert payload["model"] == "fixture-llm-1"
    assert payload["provider"] == "monkeypatched-seam"
    assert payload["status"] == "ok"
    assert "prompt" in payload["input"]
    assert payload["output"]
    assert payload["arm_id"] == "selected"
    assert payload["delta"] == {"kind": "selected_cards", "ref": "cards.json"}
    assert payload["delta_kind"] == "selected_cards"

    outcomes = [
        e
        for e in _arm_events(sdk_client, run_id, "log", correlation_id)
        if e["payload"].get("arm_outcome") is True
    ]
    assert len(outcomes) == 1
    outcome = outcomes[0]["payload"]
    assert outcome["arm_id"] == "selected"
    assert outcome["delta_kind"] == "selected_cards"
    assert outcome["outcome"] == "order_confirmed"
    assert outcome["confirmed"] is True
    assert outcome["charge"]["status"] == "succeeded"
    assert outcome["idempotency_key_used"] == "ord-20917"


# ---------------------------------------------------------------------------
# additional: the arm timeout is configuration, SDK default untouched
# ---------------------------------------------------------------------------


def test_arm_timeout_configuration(monkeypatch):
    monkeypatch.delenv("AFR_ARM_REPLAY_TIMEOUT_SECONDS", raising=False)
    assert arm_handler.recommended_timeout_seconds() == 300.0
    assert run_arms.resolve_timeout_seconds() == 300.0

    monkeypatch.setenv("AFR_ARM_REPLAY_TIMEOUT_SECONDS", "180")
    assert arm_handler.recommended_timeout_seconds() == 180.0
    assert run_arms.resolve_timeout_seconds() == 180.0

    # A CLI flag beats the env recommendation; the SDK's own default
    # (30s, read from its separate env var) is not modified by any of this.
    assert run_arms.resolve_timeout_seconds(42) == 42.0
    from afr import hooks as replay_hooks

    monkeypatch.delenv("AFR_REPLAY_TIMEOUT_SECONDS", raising=False)
    assert replay_hooks._replay_timeout_seconds() == 30.0
