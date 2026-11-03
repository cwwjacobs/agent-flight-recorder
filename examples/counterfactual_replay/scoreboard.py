"""Step 5 — the scoreboard renderer for the counterfactual replay harness.

render_scoreboard(grades, manifest) is a PURE function over the two
parsed documents: the afr.grades.v1 document (Step 3's output, as
bundled by Step 4) and the pack's manifest.json (Step 4's
afr.receipt-bundle.v1). It returns one self-contained static HTML
document — inline CSS, no JavaScript, no external assets, stdlib
only — that a browser opens and a camera can zoom.

THE STEP 4 / STEP 5 LINE (pinned in the Step 4 map, honored here):
this renderer reads grades.json and manifest.json and NOTHING
else. It recomputes no grade, re-derives no slice, opens no DB,
no server, no network, and never opens export.json, arms/, or
materials/ — render_bundle_scoreboard below loads exactly the two
permitted files, and a test proves the render is byte-identical
from a pack copy with everything else deleted. It also never
writes into the bundle: a file inside the pack is an unlisted
extra file and Step 4's own completeness check fails the pack on
it, so the driver (render_scoreboard.py) refuses an --out inside
the bundle directory.

DISPLAY HONESTY (the renderer's half of the brief's honesty
lines — the data already encodes these rules; the renderer must
not undo them at display time):
- The oracle arm renders BELOW the ranked rows, set apart and
  labeled an upper-bound reference. It never appears in the
  ranked list, never receives a rank, and the best-arm line
  never names it — even when it ties the best arm.
- A trace_invalid arm renders INVALID TRACE with dashed cells
  and the total "invalid" — never 0/6, never any number. A
  missing arm renders MISSING, an unexpected arm UNEXPECTED,
  both unscored. A partial experiment renders as a partial
  experiment; the screen cannot make a broken arm look like a
  scored zero.
- The footer states the bundle provenance and the drift line:
  a replay is a re-run, not a bit-identical copy; the score,
  not bit-identity, is the truth claim. The screen makes NO
  claim about whether the recorded run was seeded or recorded
  live — that disclosure is the demo narration's, and neither
  document this renderer may read carries the flag.

Determinism is structural: same two documents in, byte-identical
string out. Arms are emitted in score_order, then any remaining
graded rows, then the reference row, then non-graded rows in
grades-document order; assertion columns follow the grader's
SCORED_CHECKS order. No timestamps, no environment, no dict-order
luck. Every interpolated value passes html.escape — arm ids,
delta kinds/refs, and recorded facts are data, treated as
untrusted text.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from examples.counterfactual_replay import grader

#: Assertion columns, in the grader's SCORED_CHECKS order — the
#: column order is part of the grading contract, not a display
#: choice, so it is read from the grader, never re-typed here.
ASSERTION_COLUMNS: tuple[str, ...] = tuple(
    name for name, _check in grader.SCORED_CHECKS
)

_PASS_MARK = "&#10003;"  # check mark
_FAIL_MARK = "&#10007;"  # cross
_NO_MARK = "&mdash;"
_ORACLE_LABEL = "upper-bound reference, not a fair arm"

_STATUS_WORDS = {
    "trace_invalid": "INVALID TRACE",
    "missing": "MISSING",
    "unexpected": "UNEXPECTED",
}
_STATUS_TOTALS = {
    "trace_invalid": "invalid",
    "missing": "missing",
    "unexpected": "unexpected",
}

_FOOTER_LINES = (
    "Rendered from the exported receipt bundle — not live state.",
    "Oracle arm is an upper-bound reference, never a fair arm.",
    "A replay is a re-run, not a bit-identical copy. "
    "The score, not bit-identity, is the truth claim.",
)

_CSS = """
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
       margin: 2.5rem auto; max-width: 72rem; padding: 0 1.5rem;
       color: #16181d; background: #ffffff; }
h1 { font-size: 2rem; margin: 0 0 0.25rem; }
.sub { color: #444a54; margin: 0.15rem 0; font-size: 1.05rem; }
.recorded { margin: 1.25rem 0; padding: 0.75rem 1rem; font-size: 1.1rem;
            background: #fdf0ef; border-left: 0.35rem solid #b3352c; }
table { border-collapse: collapse; width: 100%; margin-top: 1rem;
        font-size: 1.15rem; }
th, td { border: 1px solid #c9ccd4; padding: 0.55rem 0.7rem;
         text-align: center; }
th { background: #eceef2; font-size: 0.95rem; }
td.arm, th.arm { text-align: left; }
td.delta, th.delta { text-align: left; color: #333a45; }
td.cell.pass { color: #146c2e; font-weight: 700; }
td.cell.fail { color: #b3352c; font-weight: 700; }
td.cell.na { color: #8a8f9a; }
td.total, th.total { font-size: 1.45rem; font-weight: 700;
                     background: #f2f5fb; min-width: 5.5rem; }
td.total.na { font-size: 1.05rem; font-weight: 600; color: #6a5a00;
              background: #fdf6dd; }
tr.reference td { background: #f7f3e6; border-top: 0.3rem double #6b6236; }
tr.reference td.total { background: #f1ead2; }
.ref-label { color: #6b6236; font-weight: 600; }
.badge { display: inline-block; margin-left: 0.5rem; padding: 0.05rem 0.45rem;
         font-size: 0.85rem; font-weight: 700; color: #6a5a00;
         background: #fdf6dd; border: 1px solid #d8c96a;
         border-radius: 0.25rem; }
.delta-line { margin-top: 1.25rem; font-size: 1.3rem; font-weight: 600; }
.digest { margin-top: 0.75rem; color: #444a54; font-size: 1.05rem; }
footer { margin-top: 2rem; padding-top: 0.75rem;
         border-top: 1px solid #c9ccd4; color: #444a54;
         font-size: 1rem; }
footer p { margin: 0.2rem 0; }
"""


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _delta_cell(delta: Any) -> str:
    """Table form of a declared delta: 'selected_cards · cards.json'."""
    delta = _as_dict(delta)
    kind = delta.get("kind")
    if not kind:
        return _NO_MARK
    ref = delta.get("ref")
    return f"{_esc(kind)} &middot; {_esc(ref) if ref else _NO_MARK}"


def _delta_phrase(delta: Any) -> str:
    """Prose form for the best-arm line: 'selected_cards (cards.json)'."""
    delta = _as_dict(delta)
    kind = delta.get("kind")
    if not kind:
        return "none"
    ref = delta.get("ref")
    return f"{_esc(kind)} ({_esc(ref)})" if ref else _esc(kind)


def _recorded_strip(recorded: Any) -> str:
    """One line naming the recorded failure every arm forked from."""
    recorded = _as_dict(recorded)
    parts: list[str] = []
    tool = recorded.get("charge_tool")
    error = recorded.get("error")
    if tool and error:
        parts.append(f"{_esc(tool)}: {_esc(error)}")
    elif tool or error:
        parts.append(_esc(tool or error))
    amount = recorded.get("amount_usd")
    if isinstance(amount, (int, float)) and not isinstance(amount, bool):
        parts.append(f"amount ${amount:,.2f}")
    elif amount is not None:
        parts.append(f"amount {_esc(amount)}")
    key = recorded.get("idempotency_key")
    if key:
        parts.append(f"idempotency key {_esc(key)}")
    if not parts:
        return ""
    return (
        '<section class="recorded"><strong>Recorded failure:</strong> '
        + " &middot; ".join(parts)
        + "</section>"
    )


def _arm_row(arm_id: str, row: Any) -> str:
    row = _as_dict(row)
    status = row.get("status")
    is_reference = row.get("role") == "reference"
    cells: list[str] = []

    arm_cell = f"<strong>{_esc(arm_id)}</strong>"
    if is_reference:
        arm_cell += f' &mdash; <span class="ref-label">{_ORACLE_LABEL}</span>'
    if status in _STATUS_WORDS:
        arm_cell += f' <span class="badge">{_STATUS_WORDS[status]}</span>'
    cells.append(f'<td class="arm">{arm_cell}</td>')
    cells.append(f'<td class="delta">{_delta_cell(row.get("delta"))}</td>')

    if status == "graded":
        assertions = _as_dict(row.get("assertions"))
        keys = list(ASSERTION_COLUMNS) + [
            key for key in assertions if key not in ASSERTION_COLUMNS
        ]
        for key in keys:
            if key not in assertions:
                cells.append(f'<td class="cell na">{_NO_MARK}</td>')
            elif assertions[key]:
                cells.append(f'<td class="cell pass">{_PASS_MARK}</td>')
            else:
                cells.append(f'<td class="cell fail">{_FAIL_MARK}</td>')
        total = f"{_esc(row.get('score'))}/{_esc(row.get('max_score'))}"
        cells.append(f'<td class="total">{total}</td>')
    else:
        # Non-graded rows are never scored: dashed cells and a
        # status word where the total would go — never a number.
        cells.extend(
            f'<td class="cell na">{_NO_MARK}</td>' for _ in ASSERTION_COLUMNS
        )
        total_word = _STATUS_TOTALS.get(status, _NO_MARK)
        cells.append(f'<td class="total na">{total_word}</td>')

    row_class = ' class="reference"' if is_reference else ""
    return (
        f'<tr data-arm="{_esc(arm_id)}"{row_class}>' + "".join(cells) + "</tr>"
    )


def _row_order(grades: dict) -> list[str]:
    """Emission order: ranked (score_order), leftover graded, the
    reference row, then non-graded rows in document order."""
    arms = _as_dict(grades.get("arms"))
    score_order = grades.get("score_order")
    if not isinstance(score_order, list):
        score_order = []

    def row_of(arm_id: str) -> dict:
        return _as_dict(arms.get(arm_id))

    emitted: list[str] = []
    for arm_id in score_order:
        row = row_of(arm_id)
        if (
            isinstance(arm_id, str)
            and arm_id in arms
            and row.get("status") == "graded"
            and row.get("role") != "reference"
        ):
            emitted.append(arm_id)
    for arm_id, row in arms.items():
        row = _as_dict(row)
        if (
            arm_id not in emitted
            and row.get("status") == "graded"
            and row.get("role") != "reference"
        ):
            emitted.append(arm_id)
    for arm_id, row in arms.items():
        if arm_id not in emitted and _as_dict(row).get("role") == "reference":
            emitted.append(arm_id)
    for arm_id in arms:
        if arm_id not in emitted:
            emitted.append(arm_id)
    return emitted


def _delta_line(grades: dict) -> str:
    """The line under the table naming the delta that separates the
    best ranked arm from bare — composed from data only."""
    arms = _as_dict(grades.get("arms"))
    score_order = grades.get("score_order")
    if not isinstance(score_order, list):
        score_order = []
    best_id = None
    for arm_id in score_order:
        row = _as_dict(arms.get(arm_id))
        if row.get("status") == "graded" and row.get("role") != "reference":
            best_id = arm_id
            break
    if best_id is None:
        inner = "Best arm: none — no arm graded."
    else:
        best = _as_dict(arms.get(best_id))
        bare = _as_dict(arms.get("bare"))
        bare_delta = bare.get("delta") if bare else {"kind": "none", "ref": None}
        score = f"{_esc(best.get('score'))}/{_esc(best.get('max_score'))}"
        inner = (
            f"Best arm: {_esc(best_id)} ({score}). "
            "The single declared delta separating it from bare: "
            f"{_delta_phrase(best.get('delta'))} vs {_delta_phrase(bare_delta)}."
        )
    return f'<p class="delta-line">{inner}</p>'


def render_scoreboard(grades: dict, manifest: dict) -> str:
    """Render the scoreboard screen from the two parsed documents.

    Pure: parsed grades + manifest in, HTML string out. Reads no
    files, recomputes nothing, consults no clock or environment.
    """
    grades = _as_dict(grades)
    manifest = _as_dict(manifest)
    grader_info = _as_dict(grades.get("grader"))

    header_bits = [
        f"run <code>{_esc(grades.get('run_id'))}</code>",
        f"fork checkpoint <code>{_esc(grades.get('fork_checkpoint_id'))}</code>",
    ]
    grader_bits = [
        _esc(grader_info.get("name")),
        _esc(grader_info.get("assertion_set")),
    ]

    column_headers = "".join(
        f"<th>{_esc(name)}</th>" for name in ASSERTION_COLUMNS
    )
    rows_html = "\n".join(
        _arm_row(arm_id, _as_dict(grades.get("arms")).get(arm_id))
        for arm_id in _row_order(grades)
    )
    footer_html = "\n".join(f"<p>{line}</p>" for line in _FOOTER_LINES)
    digest = manifest.get("bundle_digest")

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>Counterfactual Replay Scoreboard — "
        f"{_esc(grades.get('run_id'))}</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        "<h1>Counterfactual Replay Harness</h1>\n"
        f'<p class="sub">Scoreboard &middot; {" &middot; ".join(header_bits)}</p>\n'
        f'<p class="sub">Graded by {" &middot; ".join(grader_bits)}</p>\n'
        f"{_recorded_strip(grades.get('recorded'))}\n"
        "<table>\n<thead>\n<tr>"
        '<th class="arm">Arm</th><th class="delta">Declared delta</th>'
        f"{column_headers}"
        '<th class="total">Total</th></tr>\n</thead>\n<tbody>\n'
        f"{rows_html}\n"
        "</tbody>\n</table>\n"
        f"{_delta_line(grades)}\n"
        f'<p class="digest">Receipt bundle digest: <code>{_esc(digest)}</code></p>\n'
        f"<footer>\n{footer_html}\n</footer>\n"
        "</body>\n</html>\n"
    )


def load_bundle_documents(bundle_dir: str | Path) -> tuple[dict, dict]:
    """Load the ONLY two documents the renderer may read from a pack:
    grades.json and manifest.json."""
    bundle_dir = Path(bundle_dir)
    with open(bundle_dir / "grades.json", encoding="utf-8") as handle:
        grades = json.load(handle)
    with open(bundle_dir / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)
    return grades, manifest


def render_bundle_scoreboard(bundle_dir: str | Path) -> str:
    """Render a receipt bundle's scoreboard from the pack alone."""
    grades, manifest = load_bundle_documents(bundle_dir)
    return render_scoreboard(grades, manifest)
