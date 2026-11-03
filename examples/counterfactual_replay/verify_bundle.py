"""Thin driver: verify a Step 4 receipt bundle from its files alone.

This is the JUDGE's entry point: no server, no DB, no API —
files only. It recomputes the manifest's bundle_digest, checks
every payload file's SHA-256, re-grades the bundled export.json
and byte-compares the result against the bundled grades.json,
re-derives the per-arm slices, and checks the materials
snapshot. One line per check, then a verdict.

Usage:

    python examples/counterfactual_replay/verify_bundle.py pack/

Exit code: 0 on pass, 2 on fail (the first failing check is
named in the verdict line).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Resolve the repo root so `examples...` imports from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.counterfactual_replay import bundle as receipt_bundle  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_dir", help="receipt bundle directory to verify")
    args = parser.parse_args(argv)

    report = receipt_bundle.verify_receipt_bundle(args.bundle_dir)
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        suffix = f" — {check['detail']}" if check["detail"] else ""
        print(f"{check['name']}: {status}{suffix}")
    print(report["verdict"])
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
