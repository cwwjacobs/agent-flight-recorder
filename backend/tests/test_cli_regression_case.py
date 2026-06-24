from __future__ import annotations

import json

from afr_cli.regression_case import build_case_bundle, write_case_files


def test_regression_case_template_is_portable(tmp_path):
    run = {
        "id": "run-1234567890abcdef",
        "name": "checkout-agent-payment-timeout",
        "status": "failed",
        "created_at": "2026-06-24T00:00:00Z",
    }
    checkpoint = {
        "id": "ckpt-abcdef1234567890",
        "label": "before-payment-retry",
        "created_at": "2026-06-24T00:00:01Z",
        "event_seq": 3,
    }
    events = [
        {"seq": 1, "event_type": "model_call", "name": "plan", "payload": {"status": "ok"}},
        {"seq": 2, "event_type": "tool_call", "name": "charge_card", "payload": {"status": "error"}},
    ]
    state = {"cart_id": "cart_123", "payment_status": "timeout"}

    case = build_case_bundle(
        run=run,
        events=events,
        checkpoints=[checkpoint],
        checkpoint=checkpoint,
        state=state,
        case_name="checkout payment timeout",
    )
    written = write_case_files(
        tmp_path,
        case=case,
        case_name="checkout payment timeout",
    )

    assert {path.name for path in written} == {
        "README.md",
        "case.json",
        "test_regression_checkout_payment_timeout.py",
    }

    loaded = json.loads((tmp_path / "case.json").read_text())
    assert loaded["format"] == "afr.regression_case.v1"
    assert loaded["source"]["run_id"] == run["id"]
    assert loaded["source"]["checkpoint_id"] == checkpoint["id"]
    assert loaded["state"] == state
    assert loaded["contract"]["safe_by_default"] is True

    test_source = (tmp_path / "test_regression_checkout_payment_timeout.py").read_text()
    assert "placeholder" in test_source
    assert "test_checkout_payment_timeout_repaired_behavior" in test_source
