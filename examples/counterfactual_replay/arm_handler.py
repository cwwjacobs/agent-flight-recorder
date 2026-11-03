"""Counterfactual arm runner — the Step 2 resume handler for the replay harness.

One handler serves all four fixed arms (bare / generic / selected cards /
oracle). The arm is read from the replay ticket the server prepared — never
from a global — so the only difference between arms is the one declared
delta on the ticket:

    afr replay <run> --from <ckpt> --mode mock_tools \
        --handler examples.counterfactual_replay.arm_handler:resume_arm

or programmatically via the driver (run_arms.py) / afr.replay(..., arm_id=...,
delta={"kind": ..., "ref": ...}).

What the handler does, per arm:

1. Reads the fork-point state and the ticket's arm_id / delta.
2. Resolves the delta material (see DELTAS below) and builds the
   continuation prompt: fork state + task continuation + the arm's one
   material (or none).
3. Calls the model through the single module-level seam `call_model`
   (tests monkeypatch it; the suite never calls a real API).
4. Drives the scenario's tools ONLY through ctx.call_tool, so the
   server-computed tool_plan governs every tool. In mock_tools mode
   charge_customer has no recorded result (its only recorded call
   errored), so call_tool returns the handler-supplied default — that
   default IS the payment-gateway stub, and it behaves identically for
   every arm (see gateway_stub_result).
5. Emits the arm's substance as events via ctx.event_sink: one
   model_call event in the recorded shape (model, provider, input,
   output, status) and one terminal arm-outcome event. This is
   deliberate: AFR's replay plumbing otherwise records only result
   types and digests, and the Step 3 grader may read only the trace —
   if the handler did not emit these events there would be nothing
   gradeable to grade. The outcome event rides the existing "log"
   event type with an "arm_outcome": true payload marker, because the
   backend API validates event types against a fixed list.

DELTAS (material resolution)
Delta refs name plain files in the materials dir (env
AFR_ARM_MATERIALS_DIR, default: the materials/ folder next to this
module). Formats:
  - none:            no material; ref is ignored.
  - generic_context: a plain-text file, added verbatim. It must be
                     generic domain context, NOT distilled from the
                     recorded run, or the comparison would lie.
  - selected_cards:  a JSON file: a list of {"title", "body"} cards;
                     the card text is rendered into the prompt.
  - oracle_context:  a plain-text file with the known-correct
                     resolution. Upper-bound reference arm only —
                     never presented as a fair arm.
The actual demo materials are demo content, authored separately;
this module is only the mechanism.

MODEL CONFIGURATION (production wiring is verified separately)
call_model reads, at call time:
  - AFR_ARM_MODEL_BASE_URL   (default https://api.meta.ai/v1)
  - AFR_ARM_MODEL_NAME       (the model string; no default — the
                              Standard vs Contributor choice is the
                              operator's call, left unset here)
  - AFR_ARM_MODEL_API_KEY_ENV (the NAME of the env var holding the
                              API key; the key env var name itself is
                              unverified, so it is configuration,
                              not a hardcode)
Without a model name and a key, call_model raises
ArmModelNotConfigured instead of guessing.

TIMEOUT
A live arm makes real model calls, so the SDK's 30s handler default
(AFR_REPLAY_TIMEOUT_SECONDS) is too small. This module does not
change the SDK default — it exposes DEFAULT_ARM_TIMEOUT_SECONDS /
recommended_timeout_seconds() (env AFR_ARM_REPLAY_TIMEOUT_SECONDS),
and the driver applies the recommendation to its own process env
before invoking arms. Non-arm replays are unaffected.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

import afr
from afr.types import EVENT_LOG, EVENT_MODEL_CALL

# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

#: Order of magnitude a live arm needs (real model calls), vs the SDK's
#: 30s default which this build deliberately leaves untouched.
DEFAULT_ARM_TIMEOUT_SECONDS = 300.0
TIMEOUT_ENV_VAR = "AFR_ARM_REPLAY_TIMEOUT_SECONDS"
MATERIALS_DIR_ENV_VAR = "AFR_ARM_MATERIALS_DIR"

MODEL_BASE_URL_ENV_VAR = "AFR_ARM_MODEL_BASE_URL"
MODEL_NAME_ENV_VAR = "AFR_ARM_MODEL_NAME"
MODEL_API_KEY_ENV_ENV_VAR = "AFR_ARM_MODEL_API_KEY_ENV"
DEFAULT_MODEL_BASE_URL = "https://api.meta.ai/v1"
MODEL_PROVIDER_LABEL = "meta-model-api"

#: The arm-outcome event rides the "log" type (the backend's event-type
#: list is closed) and is identified by this payload marker.
ARM_OUTCOME_EVENT_TYPE = EVENT_LOG


class ArmModelNotConfigured(RuntimeError):
    """Raised when the model seam is invoked without model configuration."""


def recommended_timeout_seconds() -> float:
    """The handler-timeout the driver should apply for arm runs."""
    raw = os.environ.get(TIMEOUT_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_ARM_TIMEOUT_SECONDS
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{TIMEOUT_ENV_VAR} must be positive; got {raw!r}")
    return value


# ---------------------------------------------------------------------------
# the model seam — the ONE function tests monkeypatch
# ---------------------------------------------------------------------------


def model_config() -> dict[str, Any]:
    """Resolve model configuration from the environment, at call time."""
    key_env_name = os.environ.get(MODEL_API_KEY_ENV_ENV_VAR) or None
    return {
        "base_url": os.environ.get(MODEL_BASE_URL_ENV_VAR) or DEFAULT_MODEL_BASE_URL,
        "model": os.environ.get(MODEL_NAME_ENV_VAR) or None,
        "provider": MODEL_PROVIDER_LABEL,
        "api_key": os.environ.get(key_env_name) if key_env_name else None,
        "api_key_env": key_env_name,
    }


def call_model(prompt: str) -> dict[str, Any]:
    """Call the configured model once. THE SEAM.

    Returns {"model", "provider", "output", "status"} — the fields the
    handler records on the arm's model_call event. Tests monkeypatch
    this function so the suite never touches a real API; the live
    wiring (base URL / key env var name / model string) is verified
    against the provider before the first real arm, per the build map.
    """
    cfg = model_config()
    if not cfg["model"] or not cfg["api_key"]:
        raise ArmModelNotConfigured(
            "arm model is not configured: set "
            f"{MODEL_NAME_ENV_VAR} and {MODEL_API_KEY_ENV_ENV_VAR} (the name "
            "of the env var holding the API key) before a live arm run"
        )
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        # Hosted replay is a re-run, not bit-identical; temperature 0 is
        # requested where accepted, and the score — not bit-identity —
        # is the truth claim.
        "temperature": 0,
    }
    request = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    output = data["choices"][0]["message"]["content"]
    return {
        "model": cfg["model"],
        "provider": cfg["provider"],
        "output": output,
        "status": "ok",
    }


# ---------------------------------------------------------------------------
# delta material resolution
# ---------------------------------------------------------------------------


def materials_dir() -> Path:
    raw = os.environ.get(MATERIALS_DIR_ENV_VAR)
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent / "materials"


def resolve_delta_material(delta: dict[str, Any] | None) -> str | None:
    """Load the one declared delta's material; None for the bare arm."""
    if not delta:
        return None
    kind = delta.get("kind") or "none"
    if kind == "none":
        return None
    ref = delta.get("ref")
    if not ref:
        raise ValueError(f"delta kind {kind!r} requires a ref naming its material")
    root = materials_dir().resolve()
    path = (root / ref).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"delta ref {ref!r} escapes the materials dir")
    text = path.read_text(encoding="utf-8")
    if kind == "selected_cards":
        cards = json.loads(text)
        if not isinstance(cards, list):
            raise ValueError(f"cards file {ref!r} must be a JSON list of cards")
        blocks = []
        for card in cards:
            title = str(card.get("title", "")).strip()
            body = str(card.get("body", "")).strip()
            blocks.append(f"{title}\n{body}" if title else body)
        return "\n\n".join(blocks)
    return text


# ---------------------------------------------------------------------------
# prompt + directive parsing
# ---------------------------------------------------------------------------

_TASK_CONTINUATION = (
    "Continue the checkout from the recorded state and finish the order. "
    "Inventory is checked and the item is reserved; the remaining step is "
    "the customer charge, whose first attempt timed out with its state "
    "unknown. Decide how to proceed. If the context given to you directs "
    "a specific way to retry the charge, state it on its own line in "
    "exactly this form: idempotency_key: <key>"
)

_DIRECTIVE_RE = re.compile(r"idempotency_key\s*:\s*([A-Za-z0-9][\w.\-]*)")


def build_continuation_prompt(state: dict[str, Any], material: str | None) -> str:
    parts = [
        "Recorded state at the fork point:",
        json.dumps(state, indent=2, sort_keys=True),
        "",
        _TASK_CONTINUATION,
    ]
    if material:
        parts += ["", "Additional context for this arm:", material]
    return "\n".join(parts)


def parse_directives(output: str) -> dict[str, Any]:
    """Extract the model's declared charge directive from its output."""
    match = _DIRECTIVE_RE.search(output or "")
    if match:
        return {"idempotency_key": match.group(1)}
    return {}


# ---------------------------------------------------------------------------
# the payment-gateway stub (the handler-supplied call_tool default)
# ---------------------------------------------------------------------------


def gateway_stub_result(
    directives: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    """The mock_tools-mode gateway, as a call_tool default value.

    charge_customer's only recorded call errored, so it has no recorded
    mock result; in mock_tools mode this default is what the tool
    resolves to. THE STUB BEHAVES IDENTICALLY FOR EVERY ARM — only the
    arm's declared delta may change what the model decides:

    - a retry carrying the recorded idempotency key (the order id, as
      in the recorded charge args) resolves the original attempt and
      returns its true status: the charge succeeded exactly once;
    - any other attempt does not confirm: the provider times out
      again and the charge state stays unknown — mirroring the
      recorded failure, and risking a duplicate if pushed blindly.
    """
    order = state.get("order") or {}
    expected_key = order.get("order_id")
    used_key = directives.get("idempotency_key")
    if used_key is not None and expected_key is not None and used_key == expected_key:
        return {
            "status": "succeeded",
            "charge_id": "ch-90312",
            "amount_usd": order.get("total_usd"),
            "idempotency_key": used_key,
            "note": (
                "retry with the recorded idempotency key resolved the "
                "original attempt; charged exactly once"
            ),
        }
    return {
        "status": "timeout_unresolved",
        "error": "PaymentGatewayTimeout: provider did not respond within 30s",
        "idempotency_key": used_key,
        "note": (
            "charge state unknown: an attempt without the recorded "
            "idempotency key does not confirm the original charge"
        ),
    }


# ---------------------------------------------------------------------------
# live tool placeholders — operator wiring, never mocked away silently
# ---------------------------------------------------------------------------
# In mock_tools mode these never execute (call_tool returns the recorded
# result or the handler default). They exist so an allow-mode run fails
# loudly instead of pretending a real tool ran: wiring real tools is the
# operator's, outside this harness.


def check_inventory_live(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError(
        "live check_inventory is operator-provided; counterfactual arms "
        "run in mock_tools mode"
    )


def reserve_inventory_live(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError(
        "live reserve_inventory is operator-provided; counterfactual arms "
        "run in mock_tools mode"
    )


def charge_customer_live(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError(
        "live charge_customer is operator-provided; counterfactual arms "
        "run in mock_tools mode"
    )


# ---------------------------------------------------------------------------
# the handler
# ---------------------------------------------------------------------------


def _emit(ctx: afr.ReplayContext, event_type: str, payload: dict[str, Any]) -> None:
    if ctx.event_sink is not None:
        ctx.event_sink(event_type, payload)


def _derive_outcome(charge: Any) -> tuple[str, bool]:
    status = charge.get("status") if isinstance(charge, dict) else None
    if status == "succeeded":
        return "order_confirmed", True
    if status == "timeout_unresolved":
        return "charge_timeout_unresolved", False
    return "charge_not_confirmed", False


def resume_arm(ctx: afr.ReplayContext) -> dict[str, Any]:
    """Resume the checkout incident from the fork point as one declared arm."""
    ticket = ctx.ticket or {}
    arm_id = ticket.get("arm_id")
    delta = ticket.get("delta") or {"kind": "none", "ref": None}
    kind = delta.get("kind") or "none"

    material = resolve_delta_material(delta)
    prompt = build_continuation_prompt(ctx.state, material)

    response = call_model(prompt)
    _emit(
        ctx,
        EVENT_MODEL_CALL,
        {
            "model": response.get("model"),
            "provider": response.get("provider"),
            "input": {"prompt": prompt},
            "output": response.get("output"),
            "status": response.get("status", "ok"),
            "arm_id": arm_id,
            "delta": delta,
            "delta_kind": kind,
        },
    )

    directives = parse_directives(response.get("output") or "")

    order = ctx.state.get("order") or {}
    items = order.get("items") or [{}]
    sku = items[0].get("sku")

    # Every tool goes through call_tool: the server's tool_plan governs.
    ctx.call_tool("check_inventory", check_inventory_live, sku, default=None)
    ctx.call_tool(
        "reserve_inventory", reserve_inventory_live, sku=sku, qty=1, default=None
    )
    charge = ctx.call_tool(
        "charge_customer",
        charge_customer_live,
        customer=order.get("customer"),
        amount_usd=order.get("total_usd"),
        idempotency_key=directives.get("idempotency_key"),
        default=gateway_stub_result(directives, ctx.state),
    )

    outcome, confirmed = _derive_outcome(charge)
    result = {
        "arm_id": arm_id,
        "delta_kind": kind,
        "outcome": outcome,
        "confirmed": confirmed,
        "charge_status": charge.get("status") if isinstance(charge, dict) else None,
    }
    _emit(
        ctx,
        ARM_OUTCOME_EVENT_TYPE,
        {
            "arm_outcome": True,
            "arm_id": arm_id,
            "delta": delta,
            "delta_kind": kind,
            "outcome": outcome,
            "confirmed": confirmed,
            "charge": charge,
            "idempotency_key_used": directives.get("idempotency_key"),
        },
    )
    return result
