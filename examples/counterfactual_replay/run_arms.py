"""Thin driver: run the four fixed counterfactual arms over one fork point.

Each arm is a correlated replay on the SAME run's timeline (never a
forked child run): afr.replay(run_id, checkpoint_id, mode="mock_tools",
handler=resume_arm, arm_id=<arm>, delta={"kind": ..., "ref": ...}).
The arm's trace is the event set correlated to its own
replay_requested event — that is what the grader (Step 3) reads and
the receipt bundle (Step 4) exports.

Usage (backend running, e.g. `make serve`):

    AFR_REPLAY_ENABLED=true \
    AFR_ARM_MATERIALS_DIR=examples/counterfactual_replay/materials \
    python examples/counterfactual_replay/run_arms.py \
        --run-id <run> --checkpoint-id <ckpt>

The generic / cards / oracle refs default to the demo material file
names below; those files are demo content supplied by the operator
(see materials/README.md) — the driver fails loudly on the arm whose
material is missing rather than silently running it bare.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Resolve the repo root so `examples...` and `afr` import from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import afr  # noqa: E402

from examples.counterfactual_replay import arm_handler  # noqa: E402

#: The four fixed arms: (arm_id, delta). Exactly one delta each.
ARMS: list[tuple[str, dict]] = [
    ("bare", {"kind": "none", "ref": None}),
    ("generic", {"kind": "generic_context", "ref": "generic-checkout-context.txt"}),
    ("selected", {"kind": "selected_cards", "ref": "demo-cards.json"}),
    ("oracle", {"kind": "oracle_context", "ref": "oracle-checkout.txt"}),
]


def resolve_timeout_seconds(cli_value: float | None = None) -> float:
    """Arm handler timeout: CLI flag > arm env recommendation."""
    if cli_value is not None:
        if cli_value <= 0:
            raise ValueError("--timeout must be positive")
        return float(cli_value)
    return arm_handler.recommended_timeout_seconds()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--checkpoint-id", required=True)
    parser.add_argument("--api-url", default=None)
    parser.add_argument("--mode", default="mock_tools")
    parser.add_argument("--materials-dir", default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--generic-ref", default="generic-checkout-context.txt")
    parser.add_argument("--cards-ref", default="demo-cards.json")
    parser.add_argument("--oracle-ref", default="oracle-checkout.txt")
    args = parser.parse_args(argv)

    if os.environ.get("AFR_REPLAY_ENABLED", "").lower() not in ("1", "true", "yes"):
        print(
            "replay is disabled: set AFR_REPLAY_ENABLED=true to run arms",
            file=sys.stderr,
        )
        return 2

    if args.materials_dir:
        os.environ[arm_handler.MATERIALS_DIR_ENV_VAR] = args.materials_dir
    # Apply the arm timeout recommendation to THIS process only, before
    # any replay: the SDK reads AFR_REPLAY_TIMEOUT_SECONDS at invoke
    # time. The SDK default (30s) stays untouched for everyone else.
    os.environ["AFR_REPLAY_TIMEOUT_SECONDS"] = str(
        resolve_timeout_seconds(args.timeout)
    )

    arms = [
        ("bare", {"kind": "none", "ref": None}),
        ("generic", {"kind": "generic_context", "ref": args.generic_ref}),
        ("selected", {"kind": "selected_cards", "ref": args.cards_ref}),
        ("oracle", {"kind": "oracle_context", "ref": args.oracle_ref}),
    ]

    client = afr.AFRClient(args.api_url)
    failures = 0
    try:
        for arm_id, delta in arms:
            try:
                result = afr.replay(
                    args.run_id,
                    args.checkpoint_id,
                    mode=args.mode,
                    client=client,
                    handler=arm_handler.resume_arm,
                    arm_id=arm_id,
                    delta=delta,
                )
            except Exception as exc:  # one arm's failure must not hide the rest
                failures += 1
                print(f"[{arm_id}] FAILED: {type(exc).__name__}: {exc}")
                continue
            summary = result.get("handler_result") or {}
            print(
                f"[{arm_id}] invoked={result.get('handler_invoked')} "
                f"outcome={summary.get('outcome')} "
                f"replay_event_id={(result.get('ticket') or {}).get('replay_event_id')}"
            )
            if not result.get("handler_invoked"):
                failures += 1
    finally:
        client.close()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
