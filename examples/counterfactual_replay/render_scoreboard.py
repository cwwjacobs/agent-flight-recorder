"""Thin driver: render the Step 5 scoreboard from a receipt bundle.

The renderer (scoreboard.render_bundle_scoreboard) reads ONLY the
pack's grades.json and manifest.json and recomputes nothing — the
screen is a pure function of the bundle, never of live state.

Usage:

    python examples/counterfactual_replay/render_scoreboard.py \
        pack/ [--out scoreboard.html]

--out defaults to scoreboard.html in the current directory and
must NEVER be inside the bundle directory: a file written into
the pack is an unlisted extra file, and the pack's own
completeness check (verify_bundle.py) fails on it. The driver
refuses such an --out, in plain words, and writes nothing.

Exit code: 0 when rendered from a complete grades document
(every expected arm graded); 2 when rendered from an incomplete
one — the grades document reports missing / trace_invalid /
unexpected arms — the screen still renders, so it can SHOW the
broken arm; that is the honest picture, and the exit code carries
the incompleteness, exactly as grade_arms' 0/2. A refused --out
also exits 2, with nothing written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Resolve the repo root so `examples...` imports from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.counterfactual_replay import grader, scoreboard  # noqa: E402


def _grades_complete(grades: dict) -> bool:
    """Complete = every expected arm graded and no row ungraded."""
    arms = grades.get("arms")
    if not isinstance(arms, dict):
        return False
    expected = [arm_id for arm_id, _kind, _role in grader.EXPECTED_ARMS]
    if not all(
        isinstance(arms.get(arm_id), dict)
        and arms[arm_id].get("status") == "graded"
        for arm_id in expected
    ):
        return False
    return all(
        isinstance(row, dict) and row.get("status") == "graded"
        for row in arms.values()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_dir", help="receipt bundle directory to render")
    parser.add_argument(
        "--out",
        default="scoreboard.html",
        help="HTML output path (default: scoreboard.html in the current "
        "directory); must be OUTSIDE the bundle directory",
    )
    args = parser.parse_args(argv)

    bundle_dir = Path(args.bundle_dir)
    out_path = Path(args.out)
    resolved_bundle = bundle_dir.resolve()
    resolved_out = out_path.resolve()
    if resolved_out == resolved_bundle or resolved_bundle in resolved_out.parents:
        print(
            f"refusing to write {out_path} inside the bundle directory "
            f"{bundle_dir}: an extra file inside the pack fails the "
            "bundle's own completeness check. Choose an --out outside "
            "the pack.",
            file=sys.stderr,
        )
        return 2

    grades, manifest = scoreboard.load_bundle_documents(bundle_dir)
    out_path.write_text(
        scoreboard.render_scoreboard(grades, manifest), encoding="utf-8"
    )
    print(f"bundle_digest: {manifest.get('bundle_digest')}")
    print(f"scoreboard written to {out_path}")
    return 0 if _grades_complete(grades) else 2


if __name__ == "__main__":
    raise SystemExit(main())
