"""Thin driver: build a Step 4 receipt bundle for one fork experiment.

Input is either a run id (--run-id), exported through the SDK, or
a saved export file (--bundle — which may be an `afr export` CLI
file; parsing erases its key order). Both paths converge on the
same export dict and grade in-process via grader.grade_bundle, so
both produce byte-identical packs from the same record. The
bundled grades.json is byte-for-byte what grade_arms.py writes
from the bundled export.json.

After writing, the driver verifies its own output in-process
(bundle.verify_receipt_bundle) and prints a short summary: run
id, per-arm scores, the bundle_digest, the manifest path, and
the self-verify report.

Usage:

    python examples/counterfactual_replay/build_bundle.py \
        --bundle export.json --out-dir pack/ \
        --materials-dir examples/counterfactual_replay/materials

Exit code: 0 = built, self-verified, every expected arm graded;
2 = built and self-verified but grading incomplete (mirrors
grade_arms semantics — a bundle of a partial experiment is still
a receipt); 3 = the build failed or the pack failed its own
verify, i.e. the pack on disk is not trustworthy.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Resolve the repo root so `examples...` and `afr` import from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import afr  # noqa: E402

from examples.counterfactual_replay import bundle as receipt_bundle  # noqa: E402
from examples.counterfactual_replay import grader  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bundle", default=None, help="export JSON file to pack")
    source.add_argument("--run-id", default=None, help="run to export, then pack")
    parser.add_argument("--api-url", default=None)
    parser.add_argument(
        "--materials-dir",
        default=None,
        help="directory holding the files the tickets' delta refs name",
    )
    parser.add_argument("--out-dir", required=True, help="pack directory to write")
    args = parser.parse_args(argv)

    if args.bundle:
        export = grader.load_bundle(args.bundle)
    else:
        client = afr.AFRClient(args.api_url)
        try:
            export = client.export_bundle(args.run_id)
        finally:
            client.close()

    grades = grader.grade_bundle(export)
    try:
        manifest = receipt_bundle.build_receipt_bundle(
            export, grades, args.out_dir, materials_dir=args.materials_dir
        )
    except Exception as exc:  # a failed build must say so plainly
        print(f"build failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    report = receipt_bundle.verify_receipt_bundle(args.out_dir)
    print(f"run: {manifest['run_id']}")
    for arm_id, _kind, _role in grader.EXPECTED_ARMS:
        row = grades["arms"].get(arm_id, {})
        score = row.get("score")
        rendered = (
            f"{score}/{row.get('max_score')}" if score is not None else row.get("status")
        )
        print(f"[{arm_id}] {rendered}")
    print(f"bundle_digest: {manifest['bundle_digest']}")
    print(f"manifest: {Path(args.out_dir) / receipt_bundle.MANIFEST_NAME}")
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        suffix = f" — {check['detail']}" if check["detail"] else ""
        print(f"self-verify {check['name']}: {status}{suffix}")
    print(report["verdict"])

    if not report["ok"]:
        return 3
    expected = [arm_id for arm_id, _kind, _role in grader.EXPECTED_ARMS]
    all_graded = all(
        grades["arms"].get(arm_id, {}).get("status") == "graded" for arm_id in expected
    )
    return 0 if all_graded else 2


if __name__ == "__main__":
    raise SystemExit(main())
