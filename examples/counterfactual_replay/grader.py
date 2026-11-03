"""Step 3 — the deterministic grader for the counterfactual replay harness.

grade_bundle(bundle) is a PURE function over one AFR export document
(the afr.export.v1 dict from AFRClient.export_bundle(), or the same
JSON written by `afr export`). It grades the four fixed arms'
traces with the executable assertion set "checkout-payment-timeout.v1"
and returns an afr.grades.v1 document that Step 4 bundles and
Step 5 renders — neither needs live state to recompute it.

THE GRADING PRINCIPLE (load-bearing): deterministic oracle
assertions only. This grader NEVER interprets model output — it
does not read the model_call output text for meaning or quality.
It checks only structured, decidable facts: declared-vs-used
values, outcome fields, event presence/counts, tool-action
records. The one place model text was ever parsed is Step 2's
handler (a fixed regex extracting the declared idempotency-key
directive); the grader grades that extraction's RESULT as
recorded data (idempotency_key_used on the outcome event), it
does not re-parse text.

Expectations are DERIVED from the trace, never hardcoded: the
recorded idempotency key and amount the arms are compared
against are read at grade time from the recorded run's own
charge error event.

Determinism is structural: no clocks (created_at is never read;
ordering is by the integer seq), no randomness, no environment,
no network, no DB, no float arithmetic (amounts compared by
equality on values copied from the same record; scores are
integer counts). Same bundle in -> same grades out, byte-identical
under json.dumps(..., sort_keys=True).

The grader is TOTAL over any JSON input: a malformed or partial
trace yields failed validity checks and trace_invalid / missing
rows, never an exception. A broken trace is a grading result,
not a crash — and a trace-invalid arm is never a pass and never
a silent zero: its row is always present with score null.

The oracle arm is scored by the same assertions and its total
is shown, but it is an upper-bound REFERENCE, never a fair arm:
its row carries "role": "reference" and it is excluded from
score_order even when it ties or wins. (Corollary: a sub-max
oracle score indicts the harness or the stub, not the oracle —
its material contains the known-correct resolution by
construction.)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

#: The fixed arm set: (arm_id, declared delta kind, role). Mirrors
#: run_arms.ARMS — a test asserts the two agree so the lists
#: cannot drift apart silently.
EXPECTED_ARMS: tuple[tuple[str, str, str], ...] = (
    ("bare", "none", "control"),
    ("generic", "generic_context", "arm"),
    ("selected", "selected_cards", "arm"),
    ("oracle", "oracle_context", "reference"),
)

GRADER_NAME = "counterfactual-oracle-grader"
GRADER_VERSION = 1
ASSERTION_SET = "checkout-payment-timeout.v1"
RECORDED_CHARGE_TOOL = "charge_customer"
ARM_MODE = "mock_tools"
MAX_SCORE = 6


def load_bundle(path: str | Path) -> dict:
    """Parse an export JSON file into the dict grade_bundle grades."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# total-access helpers — the grader never raises on malformed input
# ---------------------------------------------------------------------------


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _payload(event: dict) -> dict:
    return _as_dict(event.get("payload"))


def _seq(event: dict) -> int:
    seq = event.get("seq")
    return seq if isinstance(seq, int) and not isinstance(seq, bool) else 0


# ---------------------------------------------------------------------------
# the arm trace the assertions read
# ---------------------------------------------------------------------------


class _ArmTrace:
    """One arm's slice of the flat timeline, segmented by correlation."""

    def __init__(self, ticket: dict | None, events: list[dict]):
        self.ticket = ticket
        self.ticket_payload = _payload(ticket) if ticket is not None else {}
        self.events = events
        self.model_calls = [e for e in events if e.get("event_type") == "model_call"]
        self.outcomes = [
            e
            for e in events
            if e.get("event_type") == "log" and _payload(e).get("arm_outcome") is True
        ]
        self.charge_actions = [
            e
            for e in events
            if e.get("event_type") == "replay_action"
            and _payload(e).get("tool") == RECORDED_CHARGE_TOOL
        ]

    @property
    def declared_delta(self) -> Any:
        return self.ticket_payload.get("delta")

    @property
    def outcome_payload(self) -> dict | None:
        if len(self.outcomes) != 1:
            return None
        return _payload(self.outcomes[0])


# ---------------------------------------------------------------------------
# validity assertions — any failure -> trace_invalid, never scored
# ---------------------------------------------------------------------------


def _v1_ticket_declares_arm(trace: _ArmTrace, ctx: dict) -> bool:
    if trace.ticket is None:
        return False
    if trace.ticket_payload.get("arm_id") != ctx["arm_id"]:
        return False
    delta = trace.declared_delta
    return isinstance(delta, dict) and delta.get("kind") == ctx["kind"]


def _v2_ticket_mode_mock_tools(trace: _ArmTrace, ctx: dict) -> bool:
    return trace.ticket is not None and trace.ticket_payload.get("mode") == ARM_MODE


def _v3_model_call_present(trace: _ArmTrace, ctx: dict) -> bool:
    return len(trace.model_calls) == 1


def _v4_model_call_wellformed(trace: _ArmTrace, ctx: dict) -> bool:
    if len(trace.model_calls) != 1:
        return False
    payload = _payload(trace.model_calls[0])
    prompt = _as_dict(payload.get("input")).get("prompt")
    return (
        payload.get("model") is not None
        and payload.get("provider") is not None
        and isinstance(prompt, str)
        and bool(prompt)
        and isinstance(payload.get("output"), str)
        and bool(payload.get("output"))
        and payload.get("status") == "ok"
        and payload.get("arm_id") == ctx["arm_id"]
        and payload.get("delta") == trace.declared_delta
    )


def _v5_outcome_present(trace: _ArmTrace, ctx: dict) -> bool:
    return len(trace.outcomes) == 1


def _v6_outcome_consistent(trace: _ArmTrace, ctx: dict) -> bool:
    payload = trace.outcome_payload
    if payload is None:
        return False
    return (
        payload.get("arm_id") == ctx["arm_id"]
        and payload.get("delta") == trace.declared_delta
        and payload.get("delta_kind") == _as_dict(trace.declared_delta).get("kind")
        and payload.get("confirmed") == (payload.get("outcome") == "order_confirmed")
    )


VALIDITY_CHECKS: list[tuple[str, Callable[[_ArmTrace, dict], bool]]] = [
    ("ticket_declares_arm", _v1_ticket_declares_arm),
    ("ticket_mode_mock_tools", _v2_ticket_mode_mock_tools),
    ("model_call_present", _v3_model_call_present),
    ("model_call_wellformed", _v4_model_call_wellformed),
    ("outcome_present", _v5_outcome_present),
    ("outcome_consistent", _v6_outcome_consistent),
]


# ---------------------------------------------------------------------------
# scored assertions — one named, decidable check each; max_score = 6
# ---------------------------------------------------------------------------


def _g1_order_confirmed(trace: _ArmTrace, ctx: dict) -> bool:
    payload = trace.outcome_payload or {}
    return payload.get("outcome") == "order_confirmed" and payload.get("confirmed") is True


def _g2_charge_resolved(trace: _ArmTrace, ctx: dict) -> bool:
    charge = (trace.outcome_payload or {}).get("charge")
    return isinstance(charge, dict) and charge.get("status") == "succeeded"


def _g3_single_charge_attempt(trace: _ArmTrace, ctx: dict) -> bool:
    return len(trace.charge_actions) == 1


def _g4_no_live_charge(trace: _ArmTrace, ctx: dict) -> bool:
    return all(_payload(e).get("action") != "allow" for e in trace.charge_actions)


def _g5_recorded_key_used(trace: _ArmTrace, ctx: dict) -> bool:
    recorded_key = ctx["recorded_key"]
    if recorded_key is None:
        return False
    payload = trace.outcome_payload or {}
    charge = payload.get("charge")
    return (
        payload.get("idempotency_key_used") == recorded_key
        and isinstance(charge, dict)
        and charge.get("idempotency_key") == recorded_key
    )


def _g6_amount_matches_record(trace: _ArmTrace, ctx: dict) -> bool:
    if ctx["recorded_amount"] is None:
        return False
    charge = (trace.outcome_payload or {}).get("charge")
    return isinstance(charge, dict) and charge.get("amount_usd") == ctx["recorded_amount"]


SCORED_CHECKS: list[tuple[str, Callable[[_ArmTrace, dict], bool]]] = [
    ("order_confirmed", _g1_order_confirmed),
    ("charge_resolved", _g2_charge_resolved),
    ("single_charge_attempt", _g3_single_charge_attempt),
    ("no_live_charge", _g4_no_live_charge),
    ("recorded_key_used", _g5_recorded_key_used),
    ("amount_matches_record", _g6_amount_matches_record),
]


# ---------------------------------------------------------------------------
# segmentation — derive the recorded facts and find the arms
# ---------------------------------------------------------------------------


def _find_recorded_failure(events: list[dict]) -> dict | None:
    """The recorded run's charge error event the assertions derive from."""
    for event in events:
        payload = _payload(event)
        if (
            event.get("event_type") == "tool_call"
            and payload.get("tool") == RECORDED_CHARGE_TOOL
            and payload.get("status") == "error"
        ):
            return payload
    return None


def _find_arm_tickets(events: list[dict]) -> dict[str, dict]:
    """arm_id -> its replay_requested ticket event (earliest by seq).

    Arms are ONLY replay_requested events whose payload.arm_id is
    set: the demo seed prepares one arm-less ticket of its own,
    and the recorded run's own model_call carries no correlation —
    segmentation is by ticket + correlation, never by event type
    alone.
    """
    tickets: dict[str, dict] = {}
    for event in events:
        if event.get("event_type") != "log" or event.get("name") != "replay_requested":
            continue
        arm_id = _payload(event).get("arm_id")
        if arm_id and arm_id not in tickets:
            tickets[arm_id] = event
    return tickets


def _correlated(events: list[dict], correlation_id: Any) -> list[dict]:
    if correlation_id is None:
        return []
    return [e for e in events if _payload(e).get("correlation_id") == correlation_id]


# ---------------------------------------------------------------------------
# the grader
# ---------------------------------------------------------------------------


def grade_bundle(bundle: dict) -> dict:
    """Grade one afr.export.v1 bundle. Pure and total: see module docstring."""
    bundle = _as_dict(bundle)
    raw_events = bundle.get("events")
    events = sorted(
        (e for e in raw_events if isinstance(e, dict))
        if isinstance(raw_events, list)
        else [],
        key=_seq,
    )

    recorded_payload = _find_recorded_failure(events)
    recorded_present = recorded_payload is not None
    recorded_args = _as_dict(recorded_payload.get("args")) if recorded_present else {}
    recorded = {
        "charge_tool": RECORDED_CHARGE_TOOL,
        "status": recorded_payload.get("status") if recorded_present else None,
        "error": recorded_payload.get("error") if recorded_present else None,
        "idempotency_key": recorded_args.get("idempotency_key"),
        "amount_usd": recorded_args.get("amount_usd"),
        "customer": recorded_args.get("customer"),
    }

    tickets = _find_arm_tickets(events)
    checkpoint_ids = {
        _payload(ticket).get("checkpoint_id") for ticket in tickets.values()
    }
    same_fork_point = len(checkpoint_ids) <= 1
    fork_checkpoint_id = next(iter(checkpoint_ids)) if len(checkpoint_ids) == 1 else None

    ctx_base = {
        "recorded_key": recorded["idempotency_key"],
        "recorded_amount": recorded["amount_usd"],
    }

    arms: dict[str, dict] = {}
    graded_scores: dict[str, int] = {}
    for arm_id, kind, role in EXPECTED_ARMS:
        ticket = tickets.get(arm_id)
        if ticket is None:
            arms[arm_id] = {
                "arm_id": arm_id,
                "role": role,
                "delta": {"kind": kind, "ref": None},
                "correlation_id": None,
                "status": "missing",
                "validity": {},
                "assertions": {},
                "score": None,
                "max_score": MAX_SCORE,
            }
            continue
        trace = _ArmTrace(ticket, _correlated(events, ticket.get("id")))
        ctx = {**ctx_base, "arm_id": arm_id, "kind": kind}
        validity = {name: check(trace, ctx) for name, check in VALIDITY_CHECKS}
        row: dict[str, Any] = {
            "arm_id": arm_id,
            "role": role,
            "delta": trace.declared_delta,
            "correlation_id": ticket.get("id"),
            "status": "graded",
            "validity": validity,
            "assertions": {},
            "score": None,
            "max_score": MAX_SCORE,
        }
        if not recorded_present or not all(validity.values()):
            # A broken trace — or a missing experiment premise — is
            # trace_invalid: not a pass, not a silent zero.
            row["status"] = "trace_invalid"
        else:
            assertions = {name: check(trace, ctx) for name, check in SCORED_CHECKS}
            row["assertions"] = assertions
            row["score"] = sum(1 for passed in assertions.values() if passed)
            graded_scores[arm_id] = row["score"]
        arms[arm_id] = row

    # An arm outside the fixed four is reported, never silently
    # graded: the brief fixes the arm set, and a fifth scored arm
    # would break the scoreboard contract.
    expected_ids = {arm_id for arm_id, _kind, _role in EXPECTED_ARMS}
    for arm_id, ticket in tickets.items():
        if arm_id in expected_ids:
            continue
        arms[arm_id] = {
            "arm_id": arm_id,
            "role": "unexpected",
            "delta": _payload(ticket).get("delta"),
            "correlation_id": ticket.get("id"),
            "status": "unexpected",
            "validity": {},
            "assertions": {},
            "score": None,
            "max_score": MAX_SCORE,
        }

    arm_order = {arm_id: index for index, (arm_id, _k, _r) in enumerate(EXPECTED_ARMS)}
    score_order = sorted(
        (arm_id for arm_id in graded_scores if arm_id != "oracle"),
        key=lambda arm_id: (-graded_scores[arm_id], arm_order[arm_id]),
    )

    run = _as_dict(bundle.get("run"))
    return {
        "format": "afr.grades.v1",
        "grader": {
            "name": GRADER_NAME,
            "version": GRADER_VERSION,
            "assertion_set": ASSERTION_SET,
        },
        "run_id": run.get("id"),
        "fork_checkpoint_id": fork_checkpoint_id,
        "recorded": recorded,
        "validity": {
            "recorded_failure_present": recorded_present,
            "same_fork_point": same_fork_point,
        },
        "arms": arms,
        "score_order": score_order,
    }
