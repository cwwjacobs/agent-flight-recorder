"""Step 4 receipt-bundle tests for the counterfactual replay harness.

The bundle code under test lives in examples/counterfactual_replay/
(bundle.build_receipt_bundle / bundle.verify_receipt_bundle). The
fixture trace is produced exactly the way test_arm_grader.py
produces arm traces — seeded demo incident, four arms against the
monkeypatched model seam, exported via export_bundle — so the
correct grades inside the pack are known by construction (bare
2/6, generic 2/6, selected 6/6, oracle 6/6 reference). All delta
materials are test fixtures in tmp_path, labeled as such; no demo
content is seeded and no demo/sample mode exists anywhere.

Tamper tests (3)(4)(5) operate on COPIES of the built pack in
tmp_path — the pure file-level design makes them cheap; only (1)
needs the fixture trace.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import afr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.counterfactual_replay import arm_handler, grader  # noqa: E402
from examples.counterfactual_replay import bundle as receipt_bundle  # noqa: E402

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

_EXPECTED_SCORES = {"bare": 2, "generic": 2, "selected": 6, "oracle": 6}

_ASSERTION_KEYS = {
    "order_confirmed",
    "charge_resolved",
    "single_charge_attempt",
    "no_live_charge",
    "recorded_key_used",
    "amount_matches_record",
}


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


def _copy_pack(pack: Path, dest: Path) -> Path:
    shutil.copytree(pack, dest)
    return dest


def _checks_by_name(report: dict) -> dict:
    return {check["name"]: check for check in report["checks"]}


# ---------------------------------------------------------------------------
# (1) build + verify passes; hashes recomputed independently
# ---------------------------------------------------------------------------


def test_build_and_verify_passes(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    manifest = _build_pack(four_arm_bundle, materials, pack)

    assert manifest["format"] == "afr.receipt-bundle.v1"
    assert manifest["materials_included"] is True
    assert manifest["grader"] == {
        "name": "counterfactual-oracle-grader",
        "version": 1,
        "assertion_set": "checkout-payment-timeout.v1",
    }

    # The manifest lists every payload file on disk (and nothing
    # else), and each listed hash equals an INDEPENDENT recompute
    # over the file's exact bytes inside this test.
    on_disk = {
        path.relative_to(pack).as_posix()
        for path in pack.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    assert set(manifest["files"]) == on_disk
    for relpath, entry in manifest["files"].items():
        data = (pack / relpath).read_bytes()
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["bytes"] == len(data)

    # The pack carries the known truth: per-arm grades inside the
    # pack match Step 3's hand computation.
    grades_doc = json.loads((pack / "grades.json").read_text(encoding="utf-8"))
    for arm_id, score in _EXPECTED_SCORES.items():
        assert grades_doc["arms"][arm_id]["score"] == score
        arm_row = json.loads(
            (pack / "arms" / arm_id / "grades.json").read_text(encoding="utf-8")
        )
        assert arm_row["score"] == score
        assert arm_row["arm_id"] == arm_id
    assert grades_doc["arms"]["oracle"]["role"] == "reference"

    report = receipt_bundle.verify_receipt_bundle(pack)
    assert report["ok"] is True
    assert all(check["ok"] for check in report["checks"])
    assert report["verdict"].startswith("RECEIPT BUNDLE VERIFIED")


# ---------------------------------------------------------------------------
# (2) the brief's check — re-grade from the bundle alone
# ---------------------------------------------------------------------------


def test_regrade_from_bundle_alone(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)

    # From the pack directory only — no client, no server, no DB:
    # grade the bundled export and compare BYTES with the bundled
    # grades. This is the "delete the live DB copy" check,
    # exercised at the file level where the DB is absent by
    # construction.
    export = grader.load_bundle(pack / "export.json")
    recomputed = grader.grade_bundle(export)
    recomputed_bytes = (json.dumps(recomputed, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    assert recomputed_bytes == (pack / "grades.json").read_bytes()


# ---------------------------------------------------------------------------
# (3) tamper the evidence — the hash check names the right file
# ---------------------------------------------------------------------------


def test_tamper_export_fails_naming_export(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)
    tampered = _copy_pack(pack, tmp_path / "tampered-export")

    # Flip one byte inside the recorded error string (same length,
    # so the file stays valid JSON — the hash, not the parser,
    # must catch it).
    export_path = tampered / "export.json"
    data = export_path.read_bytes()
    assert b"PaymentGatewayTimeout" in data
    export_path.write_bytes(data.replace(b"PaymentGatewayTimeout", b"PaymentGatewayTimeouu", 1))

    report = receipt_bundle.verify_receipt_bundle(tampered)
    assert report["ok"] is False
    checks = _checks_by_name(report)
    assert checks["hashes"]["ok"] is False
    assert "export.json" in checks["hashes"]["detail"]


def test_tamper_grades_fails_naming_grades_and_regrade(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)
    tampered = _copy_pack(pack, tmp_path / "tampered-grades")

    grades_path = tampered / "grades.json"
    data = grades_path.read_bytes()
    assert b'"score": 6' in data
    grades_path.write_bytes(data.replace(b'"score": 6', b'"score": 7', 1))

    report = receipt_bundle.verify_receipt_bundle(tampered)
    assert report["ok"] is False
    checks = _checks_by_name(report)
    assert checks["hashes"]["ok"] is False
    assert "grades.json" in checks["hashes"]["detail"]
    # And the re-grade comparison independently fails: the fresh
    # grade of the untampered export cannot equal the tampered
    # grades document.
    assert checks["regrade"]["ok"] is False


# ---------------------------------------------------------------------------
# (4) tamper a slice — named, while the evidence still re-grades
# ---------------------------------------------------------------------------


def test_tamper_slice_fails_but_regrade_still_passes(
    four_arm_bundle, materials, tmp_path
):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)
    tampered = _copy_pack(pack, tmp_path / "tampered-slice")

    slice_path = tampered / "arms" / "selected" / "trace.json"
    data = slice_path.read_bytes()
    assert b"ord-20917" in data
    slice_path.write_bytes(data.replace(b"ord-20917", b"ord-20918", 1))

    report = receipt_bundle.verify_receipt_bundle(tampered)
    assert report["ok"] is False
    checks = _checks_by_name(report)
    assert checks["hashes"]["ok"] is False
    assert "arms/selected/trace.json" in checks["hashes"]["detail"]
    assert checks["slices"]["ok"] is False
    # The slice was a derived view, never load-bearing: the whole
    # export still re-grades byte-identically.
    assert checks["regrade"]["ok"] is True


# ---------------------------------------------------------------------------
# (5) an unlisted extra file is flagged by name
# ---------------------------------------------------------------------------


def test_unlisted_extra_file_is_flagged(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    _build_pack(four_arm_bundle, materials, pack)
    tampered = _copy_pack(pack, tmp_path / "extra-file")
    (tampered / "notes.txt").write_text("unaccounted content", encoding="utf-8")

    report = receipt_bundle.verify_receipt_bundle(tampered)
    assert report["ok"] is False
    checks = _checks_by_name(report)
    assert checks["completeness"]["ok"] is False
    assert "notes.txt" in checks["completeness"]["detail"]


# ---------------------------------------------------------------------------
# (6) scoreboard sufficiency — the pack alone carries Step 5's table
# ---------------------------------------------------------------------------


def test_scoreboard_sufficiency_contract(four_arm_bundle, materials, tmp_path):
    pack = tmp_path / "pack"
    manifest = _build_pack(four_arm_bundle, materials, pack)

    # Step 5 reads grades.json (and at most manifest.json) and
    # recomputes nothing. Every field its table needs must be
    # present and correctly shaped HERE.
    grades_doc = json.loads((pack / "grades.json").read_text(encoding="utf-8"))

    # All four arm rows, always present.
    assert set(grades_doc["arms"]) == {"bare", "generic", "selected", "oracle"}
    for arm_id, row in grades_doc["arms"].items():
        # rows × columns: the six named assertions per graded arm
        assert set(row["assertions"]) == _ASSERTION_KEYS
        assert all(isinstance(v, bool) for v in row["assertions"].values())
        # last column: the arm total
        assert isinstance(row["score"], int)
        assert row["max_score"] == 6
        # the declared delta rides on every row
        assert row["delta"] == dict(_FIXTURE_ARMS)[arm_id]

    # The ranking Step 5 renders: oracle absent, best arm first.
    assert grades_doc["score_order"] == ["selected", "bare", "generic"]
    assert "oracle" not in grades_doc["score_order"]

    # The best-arm line's inputs: the single delta that separates
    # the best arm from bare.
    best = grades_doc["score_order"][0]
    assert grades_doc["arms"][best]["delta"]["kind"] == "selected_cards"
    assert grades_doc["arms"]["bare"]["delta"]["kind"] == "none"

    # The honesty label: the oracle is an upper-bound reference.
    assert grades_doc["arms"]["oracle"]["role"] == "reference"

    # The recorded-facts block the screen may cite.
    assert grades_doc["recorded"]["idempotency_key"] == "ord-20917"
    assert grades_doc["recorded"]["amount_usd"] == 129.0

    # What Step 5 may additionally show from the manifest.
    assert manifest["bundle_digest"]
    manifest_doc = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_doc["bundle_digest"] == manifest["bundle_digest"]


# ---------------------------------------------------------------------------
# (7) determinism — build twice, identical pack fingerprint
# ---------------------------------------------------------------------------


def test_build_twice_is_deterministic(four_arm_bundle, materials, tmp_path):
    export, _run_id, _ckpt_id = four_arm_bundle
    grades = grader.grade_bundle(export)

    first = receipt_bundle.build_receipt_bundle(
        export, grades, tmp_path / "pack-a", materials_dir=materials
    )
    second = receipt_bundle.build_receipt_bundle(
        export, grades, tmp_path / "pack-b", materials_dir=materials
    )

    assert first["files"] == second["files"]
    assert first["bundle_digest"] == second["bundle_digest"]
    for name in ("export.json", "grades.json"):
        assert (tmp_path / "pack-a" / name).read_bytes() == (
            tmp_path / "pack-b" / name
        ).read_bytes()


# ---------------------------------------------------------------------------
# (8) a missing delta material fails the build loudly (decision 1)
# ---------------------------------------------------------------------------


def test_missing_material_fails_build_loudly(four_arm_bundle, tmp_path):
    export, _run_id, _ckpt_id = four_arm_bundle
    grades = grader.grade_bundle(export)
    empty_dir = tmp_path / "no-materials"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="named by a ticket is missing"):
        receipt_bundle.build_receipt_bundle(
            export, grades, tmp_path / "pack", materials_dir=empty_dir
        )
