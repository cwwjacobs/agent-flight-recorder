"""Step 3 grader tests for the counterfactual replay harness.

The grader under test lives in examples/counterfactual_replay/
(grader.grade_bundle, a pure function over an afr.export.v1
bundle). The fixture trace is produced exactly the way
test_arm_runner.py produces arm traces — seeded demo incident,
four arms against the monkeypatched model seam, exported via
export_bundle — so the correct grades are known by construction
and hand-computed in test (1). All delta materials are test
fixtures in tmp_path, labeled as such; no demo content is seeded.

Tamper tests (3)(4)(6)(7) edit plain dicts — the pure-function
design makes that cheap; only (1)(2)(5) grade the pristine
fixture export.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import afr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.counterfactual_replay import arm_handler, grader, run_arms  # noqa: E402

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


_FIXTURE_ARMS = [
    ("bare", {"kind": "none", "ref": None}),
    ("generic", {"kind": "generic_context", "ref": "generic.txt"}),
    ("selected", {"kind": "selected_cards", "ref": "cards.json"}),
    ("oracle", {"kind": "oracle_context", "ref": "oracle.txt"}),
]


@pytest.fixture()
def four_arm_bundle(monkeypatch, api, materials, sdk_client):
    """Seed the demo, run the four fixture arms, export the bundle."""
    monkeypatch.setattr(arm_handler, "call_model", _fake_model)
    doc = api.post("/demo/seed").json()
    run_id, ckpt_id = doc["run"]["id"], doc["checkpoints"]["safe"]["id"]
    for arm_id, delta in _FIXTURE_ARMS:
        result = afr.replay(
            run_id,
            ckpt_id,
            mode="mock_tools",
            client=sdk_client,
            handler=arm_handler.resume_arm,
            arm_id=arm_id,
            delta=delta,
        )
        assert result["handler_invoked"] is True
    return sdk_client.export_bundle(run_id), run_id, ckpt_id


def _ticket_event(bundle: dict, arm_id: str) -> dict:
    for event in bundle["events"]:
        payload = event.get("payload")
        if (
            event.get("event_type") == "log"
            and event.get("name") == "replay_requested"
            and isinstance(payload, dict)
            and payload.get("arm_id") == arm_id
        ):
            return event
    raise AssertionError(f"no ticket event for arm {arm_id!r}")


_UNRESOLVED_ASSERTIONS = {
    "order_confirmed": False,
    "charge_resolved": False,
    "single_charge_attempt": True,
    "no_live_charge": True,
    "recorded_key_used": False,
    "amount_matches_record": False,
}
_RESOLVED_ASSERTIONS = {name: True for name in _UNRESOLVED_ASSERTIONS}
_ALL_VALID = {
    "ticket_declares_arm": True,
    "ticket_mode_mock_tools": True,
    "model_call_present": True,
    "model_call_wellformed": True,
    "outcome_present": True,
    "outcome_consistent": True,
}


# ---------------------------------------------------------------------------
# (1) fixture-trace grades match the hand computation
# ---------------------------------------------------------------------------


def test_fixture_trace_grades_match_hand_computation(four_arm_bundle):
    bundle, run_id, ckpt_id = four_arm_bundle

    # The grader's fixed arm set cannot drift from the driver's.
    assert [(arm_id, delta["kind"]) for arm_id, delta in run_arms.ARMS] == [
        (arm_id, kind) for arm_id, kind, _role in grader.EXPECTED_ARMS
    ]

    doc = grader.grade_bundle(bundle)
    assert doc["format"] == "afr.grades.v1"
    assert doc["grader"] == {
        "name": "counterfactual-oracle-grader",
        "version": 1,
        "assertion_set": "checkout-payment-timeout.v1",
    }
    assert doc["run_id"] == run_id
    assert doc["fork_checkpoint_id"] == ckpt_id
    assert doc["validity"] == {
        "recorded_failure_present": True,
        "same_fork_point": True,
    }
    # The recorded facts are derived from the recorded charge event.
    assert doc["recorded"] == {
        "charge_tool": "charge_customer",
        "status": "error",
        "error": "PaymentGatewayTimeout: provider did not respond within 30s",
        "idempotency_key": "ord-20917",
        "amount_usd": 129.0,
        "customer": "cus-48213",
    }

    expected = {
        "bare": ("control", _UNRESOLVED_ASSERTIONS, 2),
        "generic": ("arm", _UNRESOLVED_ASSERTIONS, 2),
        "selected": ("arm", _RESOLVED_ASSERTIONS, 6),
        "oracle": ("reference", _RESOLVED_ASSERTIONS, 6),
    }
    for arm_id, (role, assertions, score) in expected.items():
        row = doc["arms"][arm_id]
        assert row["role"] == role
        assert row["status"] == "graded"
        assert row["validity"] == _ALL_VALID
        assert row["assertions"] == assertions
        assert row["score"] == score
        assert row["max_score"] == 6
        assert row["delta"] == dict(_FIXTURE_ARMS)[arm_id]
        assert row["correlation_id"] == _ticket_event(bundle, arm_id)["id"]

    # Bare and generic tie at 2; the tie breaks by the fixed arm
    # order, and the oracle is not ranked (test 5 pins that rule).
    assert doc["score_order"] == ["selected", "bare", "generic"]


# ---------------------------------------------------------------------------
# (2) recompute-identical — dict, bytes, and file round-trip
# ---------------------------------------------------------------------------


def test_recompute_is_identical(four_arm_bundle, tmp_path):
    bundle, _run_id, _ckpt_id = four_arm_bundle

    first = grader.grade_bundle(bundle)
    second = grader.grade_bundle(bundle)
    assert first == second
    first_bytes = json.dumps(first, sort_keys=True)
    assert first_bytes == json.dumps(second, sort_keys=True)

    # The same export reloaded from a JSON file grades identically —
    # the bundle alone is sufficient, no live state involved.
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(bundle), encoding="utf-8")
    from_file = grader.grade_bundle(grader.load_bundle(export_path))
    assert json.dumps(from_file, sort_keys=True) == first_bytes


# ---------------------------------------------------------------------------
# (3) a missing model_call is a trace failure, not a pass
# ---------------------------------------------------------------------------


def test_missing_model_call_is_trace_invalid(four_arm_bundle):
    bundle, _run_id, _ckpt_id = four_arm_bundle
    baseline = grader.grade_bundle(bundle)

    tampered = copy.deepcopy(bundle)
    correlation_id = _ticket_event(tampered, "selected")["id"]
    tampered["events"] = [
        event
        for event in tampered["events"]
        if not (
            event.get("event_type") == "model_call"
            and (event.get("payload") or {}).get("correlation_id") == correlation_id
        )
    ]
    doc = grader.grade_bundle(tampered)
    row = doc["arms"]["selected"]
    assert row["status"] == "trace_invalid"
    assert row["score"] is None
    assert row["assertions"] == {}
    assert row["validity"]["model_call_present"] is False
    for arm_id in ("bare", "generic", "oracle"):
        assert doc["arms"][arm_id] == baseline["arms"][arm_id]

    # Sub-case: a corrupted (non-dict) outcome payload is also a
    # trace failure — and the grader stays total, no exception.
    corrupted = copy.deepcopy(bundle)
    for event in corrupted["events"]:
        payload = event.get("payload")
        if (
            isinstance(payload, dict)
            and payload.get("arm_outcome") is True
            and payload.get("arm_id") == "bare"
        ):
            event["payload"] = "not-a-dict"
    doc = grader.grade_bundle(corrupted)
    assert doc["arms"]["bare"]["status"] == "trace_invalid"
    assert doc["arms"]["bare"]["score"] is None
    assert doc["arms"]["bare"]["validity"]["outcome_present"] is False


# ---------------------------------------------------------------------------
# (4) a missing arm is reported, not dropped
# ---------------------------------------------------------------------------


def test_missing_arm_is_reported_not_dropped(four_arm_bundle):
    bundle, _run_id, _ckpt_id = four_arm_bundle

    tampered = copy.deepcopy(bundle)
    correlation_id = _ticket_event(tampered, "oracle")["id"]
    tampered["events"] = [
        event
        for event in tampered["events"]
        if event.get("id") != correlation_id
        and (event.get("payload") or {}).get("correlation_id") != correlation_id
    ]
    doc = grader.grade_bundle(tampered)
    row = doc["arms"]["oracle"]
    assert row["status"] == "missing"
    assert row["score"] is None
    assert row["assertions"] == {}
    assert row["correlation_id"] is None
    assert doc["arms"]["selected"]["status"] == "graded"
    assert doc["arms"]["selected"]["score"] == 6


# ---------------------------------------------------------------------------
# (5) the oracle is a reference, never ranked
# ---------------------------------------------------------------------------


def test_oracle_is_never_ranked(four_arm_bundle):
    bundle, _run_id, _ckpt_id = four_arm_bundle
    doc = grader.grade_bundle(bundle)
    # The oracle ties the best arm at max score and is still
    # excluded from the ranking — it is the ceiling, not a rival.
    assert doc["arms"]["oracle"]["score"] == 6
    assert doc["arms"]["oracle"]["role"] == "reference"
    assert "oracle" not in doc["score_order"]
    assert doc["score_order"][0] == "selected"


# ---------------------------------------------------------------------------
# (6) divergent fork points are flagged; arms still graded
# ---------------------------------------------------------------------------


def test_divergent_fork_points_are_flagged(four_arm_bundle):
    bundle, _run_id, _ckpt_id = four_arm_bundle
    baseline = grader.grade_bundle(bundle)

    tampered = copy.deepcopy(bundle)
    _ticket_event(tampered, "generic")["payload"]["checkpoint_id"] = "ckpt-divergent"
    doc = grader.grade_bundle(tampered)
    assert doc["validity"]["same_fork_point"] is False
    assert doc["validity"]["recorded_failure_present"] is True
    assert doc["fork_checkpoint_id"] is None
    # The traces are individually gradeable; only the comparison
    # claim is voided, and the flag travels with the grades.
    for arm_id in ("bare", "generic", "selected", "oracle"):
        assert doc["arms"][arm_id]["status"] == "graded"
        assert doc["arms"][arm_id]["score"] == baseline["arms"][arm_id]["score"]


# ---------------------------------------------------------------------------
# (7) the recorded key is derived from the trace, not hardcoded
# ---------------------------------------------------------------------------


def test_recorded_key_is_derived_not_hardcoded(four_arm_bundle):
    bundle, _run_id, _ckpt_id = four_arm_bundle

    tampered = copy.deepcopy(bundle)
    for event in tampered["events"]:
        payload = event.get("payload")
        if (
            event.get("event_type") == "tool_call"
            and isinstance(payload, dict)
            and payload.get("tool") == "charge_customer"
            and payload.get("status") == "error"
        ):
            payload["args"]["idempotency_key"] = "ord-99999"
    doc = grader.grade_bundle(tampered)
    assert doc["recorded"]["idempotency_key"] == "ord-99999"
    # The selected arm resolved the ORIGINAL key (ord-20917); against
    # the tampered record that no longer counts — proof every
    # comparison reads the trace rather than a constant.
    selected = doc["arms"]["selected"]
    assert selected["status"] == "graded"
    assert selected["assertions"]["recorded_key_used"] is False
    assert selected["assertions"]["amount_matches_record"] is True
    assert selected["score"] == 5
    assert doc["arms"]["bare"]["score"] == 2
