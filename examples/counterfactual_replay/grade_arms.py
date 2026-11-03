"""Thin driver: grade the four arms from one exported run bundle.

The grader (grader.grade_bundle) reads ONLY the export — the
afr.export.v1 document — never live state, so the grades written
here are exactly what anyone recomputes from the receipt bundle
alone (Step 4's check). Input is either a saved export file
(--bundle) or a run id (--run-id), which is exported through the
SDK first; both paths feed the grader the identical document.

Usage:

    python examples/counterfactual_replay/grade_arms.py \
        --bundle bundle.json --out grades.json

    python examples/counterfactual_replay/grade_arms.py \
        --run-id <run> --out grades.json

Exit code: 0 when every expected arm has status "graded", 2
otherwise — the grades document is still written either way, so
Step 4 can script against the file and the exit code alike.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Resolve the repo root so `examples...` and `afr` import from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import afr  # noqa: E402

from examples.counterfactual_replay import grader  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bundle", default=None, help="export JSON file to grade")
    source.add_argument("--run-id", default=None, help="run to export, then grade")
    parser.add_argument("--api-url", default=None)
    parser.add_argument("--out", default=None, help="grades file (default: stdout)")
    args = parser.parse_args(argv)

    if args.bundle:
        bundle = grader.load_bundle(args.bundle)
    else:
        client = afr.AFRClient(args.api_url)
        try:
            bundle = client.export_bundle(args.run_id)
        finally:
            client.close()

    grades = grader.grade_bundle(bundle)
    text = json.dumps(grades, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    expected = [arm_id for arm_id, _kind, _role in grader.EXPECTED_ARMS]
    all_graded = all(
        grades["arms"].get(arm_id, {}).get("status") == "graded" for arm_id in expected
    )
    return 0 if all_graded else 2


if __name__ == "__main__":
    raise SystemExit(main())
