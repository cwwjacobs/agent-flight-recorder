"""The seeded demo incident: `checkout-agent-payment-timeout`.

One canonical, realistic failed run that shows the whole product in ~60
seconds: a checkout agent plans, reserves inventory, checkpoints *before*
the dangerous step, then the payment call times out. Replaying from the
pre-charge checkpoint in mock_tools mode demonstrates the pitch — you can
debug from before the side effect without charging a customer twice.

Seeded via POST /demo/seed (default on; AFR_DEMO_SEED_ENABLED=false to
disable) or `make demo-docker` / scripts/seed_demo_run.py over HTTP.
"""

from __future__ import annotations

from typing import Any

from app.engine import checkpoints as ckpt_engine
from app.engine import events as event_engine
from app.engine import runs as run_engine
from app.replay import prepare_replay

DEMO_RUN_NAME = "checkout-agent-payment-timeout"

CHECKPOINT_SAFE = "safe-before-side-effect"
CHECKPOINT_FAILURE = "failure-state"

_ORDER = {
    "order_id": "ord-20917",
    "customer": "cus-48213",
    "items": [{"sku": "SKU-ORCHID-01", "qty": 1, "unit_price_usd": 129.0}],
    "total_usd": 129.0,
}


def seed_demo_run() -> dict[str, Any]:
    run = run_engine.create_run(
        name=DEMO_RUN_NAME,
        metadata={"demo": True, "agent": "checkout-agent", "env": "demo"},
    )
    run_id = run["id"]

    event_engine.append_event(
        run_id,
        "log",
        name="info",
        payload={"level": "info", "message": "checkout agent started", "data": {"order": _ORDER["order_id"]}},
    )

    event_engine.append_event(
        run_id,
        "model_call",
        name="plan_checkout",
        payload={
            "model": "demo-llm-1",
            "provider": "canned",
            "input": {"prompt": "Plan checkout for order ord-20917 (1× SKU-ORCHID-01, $129)."},
            "output": "1) verify inventory 2) reserve item 3) charge customer 4) confirm order",
            "status": "ok",
            "duration_ms": 412.7,
            "usage": {"prompt_tokens": 184, "completion_tokens": 42, "total_tokens": 226},
        },
    )

    event_engine.append_event(
        run_id,
        "tool_call",
        name="check_inventory",
        payload={
            "tool": "check_inventory",
            "policy": "safe",
            "args": {"sku": "SKU-ORCHID-01"},
            "result": {"sku": "SKU-ORCHID-01", "available": 7, "warehouse": "fra-2"},
            "status": "ok",
            "duration_ms": 38.2,
        },
    )

    event_engine.append_event(
        run_id,
        "state_snapshot",
        name="state",
        payload={
            "state": {
                "order": _ORDER,
                "inventory": {"SKU-ORCHID-01": {"available": 7, "warehouse": "fra-2"}},
                "step": "inventory_checked",
            },
            "mode": "replace",
        },
    )

    event_engine.append_event(
        run_id,
        "tool_call",
        name="reserve_inventory",
        payload={
            "tool": "reserve_inventory",
            "policy": "side_effecting",
            "args": {"sku": "SKU-ORCHID-01", "qty": 1},
            "result": {"reservation_id": "rsv-7841", "expires_in_s": 900},
            "status": "ok",
            "duration_ms": 96.4,
        },
    )

    event_engine.append_event(
        run_id,
        "state_snapshot",
        name="state",
        payload={
            "state": {"reservation": {"id": "rsv-7841", "expires_in_s": 900}, "step": "reserved"},
            "mode": "merge",
        },
    )

    safe_ckpt = ckpt_engine.create_checkpoint(run_id, label=CHECKPOINT_SAFE)

    event_engine.append_event(
        run_id,
        "tool_call",
        name="charge_customer",
        payload={
            "tool": "charge_customer",
            "policy": "requires_approval",
            "args": {"customer": "cus-48213", "amount_usd": 129.0, "idempotency_key": "ord-20917"},
            "status": "error",
            "error": "PaymentGatewayTimeout: provider did not respond within 30s",
            "duration_ms": 30001.5,
        },
    )

    event_engine.append_event(
        run_id,
        "error",
        name="error",
        payload={
            "message": "payment provider timed out — charge state unknown, customer may or may not have been billed",
            "data": {"order": _ORDER["order_id"], "tool": "charge_customer"},
        },
    )

    event_engine.append_event(
        run_id,
        "state_snapshot",
        name="state",
        payload={
            "state": {"step": "charge_failed", "charge": {"status": "unknown", "attempts": 1}},
            "mode": "merge",
        },
    )

    failure_ckpt = ckpt_engine.create_checkpoint(run_id, label=CHECKPOINT_FAILURE)

    # the replay the demo story is about: resume from before the charge with
    # every tool mocked — free mode, works on free and premium instances
    ticket = prepare_replay(run_id, safe_ckpt["id"], mode="mock_tools")

    run = run_engine.end_run(run_id, status="failed")

    return {
        "run": run,
        "checkpoints": {"safe": safe_ckpt, "failure": failure_ckpt},
        "replay": ticket.to_dict(),
        "ui_url": f"/#/runs/{run_id}",
    }
