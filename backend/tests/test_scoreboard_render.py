"""Step 5 scoreboard-renderer tests for the counterfactual replay harness.

The renderer under test lives in examples/counterfactual_replay/
(scoreboard.render_scoreboard / scoreboard.render_bundle_scoreboard,
driven by render_scoreboard.py). The fixture bundle is produced
exactly the way test_receipt_bundle.py produces its pack — seeded
demo incident, four arms against the monkeypatched model seam,
exported and bundled via Step 4 — so the correct grades the screen
must show are known by construction (bare 2/6, generic 2/6,
selected 6/6, oracle 6/6 reference). All delta materials are test
fixtures in tmp_path, labeled as such; no demo content is authored
and no demo/sample mode exists anywhere.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import afr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.counterfactual_replay import arm_handler, grader, scoreboard  # noqa: E402
from examples.counterfactual_replay import bundle as receipt_bundle  # noqa: E402
from examples.counterfactual_replay import render_scoreboard as render_driver  # noqa: E402

_DIRECTIVE_IN_PROMPT = re.compile(r"idempotency_key:\s*(ord-[\w\-]+)")


def _fake_model(prompt: str) -> dict:
    match = _DIRECTIVE_IN_PROMPT.search(prompt)
    if match:
        decision = f"Retry the charge with the recorded key.\nidempotency_key: {match.group(1)}"
    else:
        decision = "Proceed with a fresh charge attempt for the order."
    return {
        "model": "fixture-llm-1",
        "provider": "monkeypatched-seam",
        "output": f"Continue the checkout.\n{decision}",
        "status": "ok",
    }


@pytest.fixture()
def sdk_client(api: TestClient) -> afr.AFRClient:
    return afr.AFRClient(http_client=api)


@pytest.fixture()
def materials(tmp_path: Path, monkeypatch) -> Path:
    """Fixture delta materials — test data, not demo content."""
    (tmp_path / "generic.txt").write_text(
        "Checkout guidance: verify inventory before charging, keep the "
        "customer informed, and confirm the order once payment settles. "
        "Standard payment retries use exponential backoff.",
        encoding="utf-8",
    )
    (tmp_path / "cards.json").write_text(
        '[{"title": "Payment timeout recovery", "body": "When a charge '
        "times out, the charge state is unknown. Retry with the recorded "
        "idempotency_key: ord-20917 to resolve the original attempt "
        'instead of charging again."}]',
        encoding="utf-8",
    )
    (tmp_path / "oracle.txt").write_text(
        "Known-correct resolution: the original charge attempt used "
        "idempotency_key: ord-20917. Retry the charge with that key; "
        "the gateway resolves the original attempt, which succeeded.",
        encoding="utf-8",
    )
    monkeypatch.setenv("AFR_ARM_MATERIALS_DIR", str(tmp_path))
    return tmp_path


_FIXTURE_ARMS = [
    ("bare", {"kind": "none", "ref": None}),
    ("generic", {"kind": "generic_context", "ref": "generic.txt"}),
    ("selected", {"kind": "selected_cards", "ref": "cards.json"}),
    ("oracle", {"kind": "oracle_context", "ref": "oracle.txt"}),
]

_ASSERTION_KEYS = [
    "order_confirmed",
    "charge_resolved",
    "single_charge_attempt",
    "no_live_charge",
    "recorded_key_used",
    "amount_matches_record",
]


@pytest.fixture()
def four_arm_bundle(monkeypatch, api, materials, sdk_client):
    """Seed the demo, run the four fixture arms, export the bundle."""
    monkeypatch.setattr(arm_handler, "call_model", _fake_model)
    doc = api.post("/demo/seed").json()
    run_id, ckpt_id = doc["run"]["id"], doc["checkpoints"]["safe"]["id"]
    for arm_id, delta in _FIXTURE_ARMS:
        result = afr.replay(
            run_id,
            ckpt_id,
            mode="mock_tools",
            client=sdk_client,
            handler=arm_handler.resume_arm,
            arm_id=arm_id,
            delta=delta,
        )
        assert result["handler_invoked"] is True
    return sdk_client.export_bundle(run_id), run_id, ckpt_id


def _build_pack(four_arm_bundle, materials: Path, out_dir: Path) -> dict:
    export, _run_id, _ckpt_id = four_arm_bundle
    grades = grader.grade_bundle(export)
    return receipt_bundle.build_receipt_bundle(
        export, grades, out_dir, materials_dir=materials
    )


def _row_html(html_text: str, arm_id: str) -> str:
    """The <tr>...</tr> slice for one arm row."""
    start = html_text.index(f'data-arm="{arm_id}"')
    end = html_text.index("</tr>", start)
    return html_text[start:end]


def _delta_line(html_text: str) -> str:
    start = html_text.index('class="delta-line"')
    end = html_text.index("</p>", start)
    return html_text[start:end]


# ---------------------------------------------------------------------------
# (1) renders from a fixture bundle — rows, columns, totals, order
# ---------------------------------------------------------------------------


def test_renders_from_fixture_bundle(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    manifest = _build_pack(four_arm_bundle, materials, pack)

    html_text = scoreboard.render_bundle_scoreboard(pack)

    # All four arm rows, all six assertion column headers.
    for arm_id, _delta in _FIXTURE_ARMS:
        assert f'data-arm="{arm_id}"' in html_text
    for key in _ASSERTION_KEYS:
        assert f"<th>{key}</th>" in html_text

    # The fixture's known totals, on the right rows.
    assert "2/6" in _row_html(html_text, "bare")
    assert "2/6" in _row_html(html_text, "generic")
    assert "6/6" in _row_html(html_text, "selected")
    assert "6/6" in _row_html(html_text, "oracle")

    # score_order respected — selected before bare before generic —
    # and the pack's fingerprint is on the screen.
    positions = {
        arm_id: html_text.index(f'data-arm="{arm_id}"')
        for arm_id, _delta in _FIXTURE_ARMS
    }
    assert positions["selected"] < positions["bare"] < positions["generic"]
    assert manifest["bundle_digest"] in html_text

    # The delta line names the best arm and its separating delta.
    line = _delta_line(html_text)
    assert "Best arm: selected (6/6)" in line
    assert "selected_cards" in line
    assert "vs none" in line


# ---------------------------------------------------------------------------
# (2) the oracle is a reference, never ranked
# ---------------------------------------------------------------------------


def test_oracle_is_reference_never_ranked(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)

    html_text = scoreboard.render_bundle_scoreboard(pack)

    # The oracle row sits BELOW every ranked row, labeled exactly.
    oracle_pos = html_text.index('data-arm="oracle"')
    for arm_id in ("selected", "bare", "generic"):
        assert html_text.index(f'data-arm="{arm_id}"') < oracle_pos
    oracle_row = _row_html(html_text, "oracle")
    assert "upper-bound reference, not a fair arm" in oracle_row

    # Both selected and oracle score 6/6 on the fixture — and the
    # best-arm line still names selected, never the oracle.
    line = _delta_line(html_text)
    assert "selected" in line
    assert "oracle" not in line


# ---------------------------------------------------------------------------
# (3) invalid is not zero — broken arms render as broken, unscored
# ---------------------------------------------------------------------------


def test_invalid_and_missing_render_unscored(four_arm_bundle):
    export, _run_id, _ckpt_id = four_arm_bundle
    grades = grader.grade_bundle(export)
    grades = copy.deepcopy(grades)
    # Edit the fixture grades the way test_arm_grader builds its
    # cases: one arm's trace broke, one arm never ran.
    grades["arms"]["generic"].update(
        status="trace_invalid", assertions={}, score=None
    )
    grades["arms"]["selected"].update(status="missing", assertions={}, score=None)

    html_text = scoreboard.render_scoreboard(grades, {"bundle_digest": "0" * 64})

    assert "INVALID TRACE" in html_text
    assert "MISSING" in html_text

    generic_row = _row_html(html_text, "generic")
    assert "INVALID TRACE" in generic_row
    assert ">invalid<" in generic_row
    assert re.search(r"\d+/\d+", generic_row) is None

    selected_row = _row_html(html_text, "selected")
    assert "MISSING" in selected_row
    assert ">missing<" in selected_row
    assert re.search(r"\d+/\d+", selected_row) is None

    # No arm scored zero on this document, so a zero total must
    # appear NOWHERE — a broken trace is never rendered as one.
    assert "0/6" not in html_text


# ---------------------------------------------------------------------------
# (4) bundle-only purity — grades.json + manifest.json and nothing else
# ---------------------------------------------------------------------------


def test_render_reads_only_grades_and_manifest(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)
    full_html = scoreboard.render_bundle_scoreboard(pack)

    stripped = tmp_path / "stripped-pack"
    shutil.copytree(pack, stripped)
    (stripped / "export.json").unlink()
    shutil.rmtree(stripped / "arms")
    shutil.rmtree(stripped / "materials")

    # With the evidence, the slices, and the materials deleted,
    # the render is byte-identical — the renderer read the two
    # permitted documents and recomputed nothing.
    assert scoreboard.render_bundle_scoreboard(stripped) == full_html


# ---------------------------------------------------------------------------
# (5) determinism + escaping — data is untrusted text
# ---------------------------------------------------------------------------


def test_render_is_deterministic_and_escapes(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)
    grades = json.loads((pack / "grades.json").read_text(encoding="utf-8"))
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))

    first = scoreboard.render_scoreboard(grades, manifest)
    second = scoreboard.render_scoreboard(grades, manifest)
    assert first == second

    hostile = copy.deepcopy(grades)
    hostile["arms"]["selected"]["delta"] = {
        "kind": "selected_cards",
        "ref": 'cards"><script>alert(1)</script>',
    }
    rendered = scoreboard.render_scoreboard(hostile, manifest)
    assert "<script>alert(1)" not in rendered
    assert "&lt;script&gt;" in rendered


# ---------------------------------------------------------------------------
# driver checks — the --out-inside-bundle refusal, and a render that
# leaves the pack verifiable
# ---------------------------------------------------------------------------


def test_driver_refuses_out_inside_bundle(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)

    inside = pack / "scoreboard.html"
    assert render_driver.main([str(pack), "--out", str(inside)]) == 2
    assert not inside.exists()

    nested = pack / "arms" / "scoreboard.html"
    assert render_driver.main([str(pack), "--out", str(nested)]) == 2
    assert not nested.exists()


def test_driver_writes_outside_bundle_and_pack_still_verifies(
    four_arm_bundle, materials, tmp_path
):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)

    out = tmp_path / "scoreboard.html"
    assert render_driver.main([str(pack), "--out", str(out)]) == 0
    html_text = out.read_text(encoding="utf-8")
    assert 'data-arm="selected"' in html_text
    assert "Best arm: selected (6/6)" in html_text

    # The pack itself is untouched by the render: it still
    # verifies, files-only, with no extra file inside it.
    report = receipt_bundle.verify_receipt_bundle(pack)
    assert report["ok"] is True
