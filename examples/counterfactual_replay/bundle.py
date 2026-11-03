"""Step 4 — the receipt bundle: a self-contained, recomputable pack.

One pack per fork experiment: the original run export (the
afr.export.v1 document), the grades (the afr.grades.v1 document,
byte-for-byte what grade_arms.py writes from that export), one
sub-bundle per arm (trace slice + delta declaration + grades row),
an optional snapshot of the delta materials, and a manifest with
a SHA-256 hash of every payload file. A judge must be able to
recompute every grade from the bundle alone, with no trust in
the harness and no live state — verify_receipt_bundle below is
that recompute, and it reads files only: no server, no DB, no
network. That absence is the brief's "delete the live DB copy"
check, exercised by construction.

HASH CONTRACT
- Algorithm: SHA-256, lowercase hex (hashlib) — the codebase's
  digest algorithm. For files: sha256 over the file's EXACT
  BYTES on disk. No repr, no re-serialization at verify time.
- Canonical bytes: every JSON payload file is written by
  canonical_json_bytes — json.dumps(obj, indent=2,
  sort_keys=True) + "\n", the grade_arms serialization — so
  each file's hash is a pure function of its content and anyone
  can regenerate identical bytes from the parsed documents.
  Materials copies are hashed as copied: their bytes are
  whatever the run actually used.
- The per-arm slices (arms/<arm_id>/) are EXTRACTED VIEWS,
  hashed so tampering is detectable but never load-bearing:
  verify re-derives them from export.json + grades.json and
  compares bytes, so a slice cannot smuggle a claim the whole
  export does not support.
- bundle_digest = sha256 over the UTF-8 bytes of the lines
  "<path>\t<sha256>\n" for every entry in the manifest's files
  table, paths sorted. One fingerprint for the whole pack,
  quotable outside it (the manifest itself is deliberately not
  self-hashed — a file cannot carry its own hash; what pins
  the manifest is quoting bundle_digest in submission text).
- No timestamps and no host/user provenance in the manifest:
  the pack is a deterministic function of the stored record
  alone, so building twice from the same export yields an
  identical bundle_digest.

Build and grade stay separate, inspectable steps: the CALLER
grades via grader.grade_bundle(export) and hands both documents
in; this module sequences file writing and owns the verify path.
Step 5 renders the scoreboard from grades.json alone and
recomputes nothing — the bundle-sufficiency contract is pinned
by a test in backend/tests/test_receipt_bundle.py.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from examples.counterfactual_replay import grader

BUNDLE_FORMAT = "afr.receipt-bundle.v1"
ARM_TRACE_FORMAT = "afr.arm-trace.v1"
MANIFEST_NAME = "manifest.json"


# ---------------------------------------------------------------------------
# canonical bytes + digests
# ---------------------------------------------------------------------------


def canonical_json_bytes(obj: Any) -> bytes:
    """The grade_arms canonical serialization, as UTF-8 bytes."""
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def file_digest(path: str | Path) -> str:
    """SHA-256 hex over the file's exact bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _bytes_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bundle_digest(files: dict[str, dict]) -> str:
    lines = "".join(f"{path}\t{files[path]['sha256']}\n" for path in sorted(files))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# arm segmentation — mirrors grader.py: an arm is a replay_requested
# ticket event whose payload.arm_id is set; its trace is the timeline
# events correlated to that ticket's id, ordered by seq.
# ---------------------------------------------------------------------------


def _payload(event: dict) -> dict:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _seq(event: dict) -> int:
    seq = event.get("seq")
    return seq if isinstance(seq, int) and not isinstance(seq, bool) else 0


def _sorted_events(export: dict) -> list[dict]:
    raw = export.get("events")
    events = (
        [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []
    )
    return sorted(events, key=_seq)


def _arm_tickets(export: dict) -> dict[str, dict]:
    """arm_id -> its ticket event (earliest by seq), as the grader finds them."""
    tickets: dict[str, dict] = {}
    for event in _sorted_events(export):
        if event.get("event_type") != "log" or event.get("name") != "replay_requested":
            continue
        arm_id = _payload(event).get("arm_id")
        if arm_id and arm_id not in tickets:
            tickets[arm_id] = event
    return tickets


def arm_slice(export: dict, arm_id: str) -> dict:
    """The arm's sub-bundle trace: ticket event + its correlated events.

    A VIEW of export.json, clearly labeled — not an afr.export.v1
    document and never a grader input (a slice cannot re-grade:
    the grader needs the recorded event and every arm).
    """
    tickets = _arm_tickets(export)
    ticket = tickets[arm_id]
    correlation_id = ticket.get("id")
    correlated = [
        event
        for event in _sorted_events(export)
        if event is not ticket
        and _payload(event).get("correlation_id") == correlation_id
    ]
    run = export.get("run")
    return {
        "format": ARM_TRACE_FORMAT,
        "run_id": run.get("id") if isinstance(run, dict) else None,
        "arm_id": arm_id,
        "correlation_id": correlation_id,
        "events": sorted([ticket, *correlated], key=_seq),
    }


def arm_delta(export: dict, arm_id: str) -> dict:
    """The arm's declared delta, copied from its ticket payload.

    An EXTRACTION from the trace — never a second source that
    could disagree with it.
    """
    ticket = _arm_tickets(export)[arm_id]
    payload = _payload(ticket)
    return {
        "arm_id": arm_id,
        "delta": payload.get("delta"),
        "mode": payload.get("mode"),
        "checkpoint_id": payload.get("checkpoint_id"),
        "correlation_id": ticket.get("id"),
    }


def arm_grades(grades: dict, arm_id: str) -> dict:
    """The arm's grades row, self-describing out of context."""
    row = grades["arms"][arm_id]
    doc = {
        "format": grades.get("format"),
        "grader": grades.get("grader"),
        "run_id": grades.get("run_id"),
        "fork_checkpoint_id": grades.get("fork_checkpoint_id"),
    }
    doc.update(row)
    return doc


def _arm_refs(export: dict) -> dict[str, str]:
    """arm_id -> delta ref filename, for arms whose delta names material."""
    refs: dict[str, str] = {}
    for arm_id, ticket in _arm_tickets(export).items():
        delta = _payload(ticket).get("delta")
        if isinstance(delta, dict) and delta.get("ref"):
            refs[arm_id] = delta["ref"]
    return refs


# ---------------------------------------------------------------------------
# the builder
# ---------------------------------------------------------------------------


def build_receipt_bundle(
    export: dict,
    grades: dict,
    out_dir: str | Path,
    materials_dir: str | Path | None = None,
) -> dict:
    """Write the pack under out_dir and return the manifest dict.

    Payload files first, manifest LAST (it hashes files that must
    already be final). Grades are computed by the caller via
    grader.grade_bundle(export) — grading is not hidden inside
    the builder. When materials_dir is given, the exact files the
    tickets' refs name are copied byte-for-byte under materials/;
    a ref'd file missing there fails the build loudly — a pack
    whose delta substance cannot be inspected must not ship
    quietly.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def write_payload(relpath: str, data: bytes) -> None:
        path = out / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        written.append(relpath)

    write_payload("export.json", canonical_json_bytes(export))
    write_payload("grades.json", canonical_json_bytes(grades))

    for arm_id in sorted(_arm_tickets(export)):
        write_payload(
            f"arms/{arm_id}/trace.json",
            canonical_json_bytes(arm_slice(export, arm_id)),
        )
        write_payload(
            f"arms/{arm_id}/delta.json",
            canonical_json_bytes(arm_delta(export, arm_id)),
        )
        write_payload(
            f"arms/{arm_id}/grades.json",
            canonical_json_bytes(arm_grades(grades, arm_id)),
        )

    materials_included = materials_dir is not None
    if materials_included:
        source_dir = Path(materials_dir)
        for ref in sorted(set(_arm_refs(export).values())):
            source = source_dir / ref
            if not source.is_file():
                raise FileNotFoundError(
                    f"delta material {ref!r} named by a ticket is missing "
                    f"from materials dir {source_dir} — refusing to build "
                    "a pack whose delta substance cannot be inspected"
                )
            write_payload(f"materials/{ref}", source.read_bytes())

    files: dict[str, dict] = {}
    for relpath in sorted(written):
        data = (out / relpath).read_bytes()
        files[relpath] = {"sha256": _bytes_digest(data), "bytes": len(data)}

    run = export.get("run")
    manifest = {
        "format": BUNDLE_FORMAT,
        "run_id": run.get("id") if isinstance(run, dict) else None,
        "fork_checkpoint_id": grades.get("fork_checkpoint_id"),
        "grader": grades.get("grader"),
        "materials_included": materials_included,
        "files": files,
        "bundle_digest": _bundle_digest(files),
    }
    (out / MANIFEST_NAME).write_bytes(canonical_json_bytes(manifest))
    return manifest


# ---------------------------------------------------------------------------
# the verify path — files only: no server, no DB, no network
# ---------------------------------------------------------------------------


def _check(name: str, ok: bool, detail: str | None = None) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _report(bundle_dir: Path, checks: list[dict]) -> dict:
    failed = next((c for c in checks if not c["ok"]), None)
    if failed is None:
        verdict = (
            "RECEIPT BUNDLE VERIFIED — grades recompute byte-identically "
            "from the bundled traces"
        )
    else:
        suffix = f": {failed['detail']}" if failed["detail"] else ""
        verdict = f"RECEIPT BUNDLE FAILED — {failed['name']}{suffix}"
    return {
        "bundle_dir": str(bundle_dir),
        "ok": failed is None,
        "checks": checks,
        "verdict": verdict,
    }


def verify_receipt_bundle(bundle_dir: str | Path) -> dict:
    """Recompute the pack from its files alone. Returns a report dict.

    Checks, in order: manifest well-formed + bundle_digest
    recomputes; completeness both ways; per-file hashes (first
    mismatch named); RE-GRADE — grade the bundled export.json
    and byte-compare against the bundled grades.json; slice
    honesty — arms/* re-derived and byte-compared; materials —
    every ticket ref resolves inside the pack and is listed.
    Each check is recorded independently where the pack's state
    allows it, so one tamper can fail several checks by name.
    """
    root = Path(bundle_dir)
    checks: list[dict] = []

    # 1. Manifest well-formed + bundle_digest recomputes.
    manifest = None
    try:
        manifest = json.loads((root / MANIFEST_NAME).read_bytes().decode("utf-8"))
    except Exception as exc:  # unreadable manifest: nothing else is decidable
        checks.append(_check("manifest", False, f"{MANIFEST_NAME}: {exc}"))
        return _report(root, checks)
    files_table = manifest.get("files") if isinstance(manifest, dict) else None
    manifest_ok = (
        isinstance(manifest, dict)
        and manifest.get("format") == BUNDLE_FORMAT
        and isinstance(files_table, dict)
        and all(
            isinstance(entry, dict) and "sha256" in entry and "bytes" in entry
            for entry in files_table.values()
        )
    )
    detail = None
    if manifest_ok and manifest.get("bundle_digest") != _bundle_digest(files_table):
        manifest_ok = False
        detail = "bundle_digest does not recompute from the files table"
    elif not manifest_ok:
        detail = f"{MANIFEST_NAME} is not a well-formed {BUNDLE_FORMAT} document"
    checks.append(_check("manifest", manifest_ok, detail))
    if not manifest_ok:
        return _report(root, checks)

    # 2. Completeness both ways: listed == on disk (manifest excepted).
    on_disk = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != MANIFEST_NAME
    }
    listed = set(files_table)
    missing = sorted(listed - on_disk)
    extra = sorted(on_disk - listed)
    if missing:
        checks.append(
            _check("completeness", False, f"{missing[0]} listed but not on disk")
        )
    elif extra:
        checks.append(
            _check("completeness", False, f"{extra[0]} on disk but not listed")
        )
    else:
        checks.append(_check("completeness", True))

    # 3. Hash check: exact bytes, first mismatch named.
    hash_detail = None
    for relpath in sorted(files_table):
        path = root / relpath
        if not path.is_file():
            hash_detail = f"{relpath}: listed but not on disk"
            break
        if file_digest(path) != files_table[relpath]["sha256"]:
            hash_detail = f"{relpath}: sha256 mismatch"
            break
    checks.append(_check("hashes", hash_detail is None, hash_detail))

    # The bundled documents, parsed once for the remaining checks.
    export = None
    try:
        export = json.loads((root / "export.json").read_bytes().decode("utf-8"))
    except Exception:
        export = None
    bundled_grades_bytes = None
    grades_path = root / "grades.json"
    if grades_path.is_file():
        bundled_grades_bytes = grades_path.read_bytes()

    # 4. RE-GRADE: the brief's check, on the files alone.
    if export is None:
        checks.append(_check("regrade", False, "export.json: unreadable"))
    elif bundled_grades_bytes is None:
        checks.append(_check("regrade", False, "grades.json: unreadable"))
    else:
        recomputed = canonical_json_bytes(grader.grade_bundle(export))
        checks.append(
            _check(
                "regrade",
                recomputed == bundled_grades_bytes,
                None
                if recomputed == bundled_grades_bytes
                else "grades.json does not match a fresh grade of export.json",
            )
        )

    # 5. Slice honesty: re-derive every arms/* file and compare bytes.
    slice_detail = None
    if export is None:
        slice_detail = "export.json: unreadable, slices cannot be re-derived"
    else:
        try:
            grades_doc = (
                json.loads(bundled_grades_bytes.decode("utf-8"))
                if bundled_grades_bytes is not None
                else None
            )
        except Exception:
            grades_doc = None
        if grades_doc is None:
            slice_detail = "grades.json: unreadable, slices cannot be re-derived"
        else:
            expected: dict[str, bytes] = {}
            try:
                for arm_id in sorted(_arm_tickets(export)):
                    expected[f"arms/{arm_id}/trace.json"] = canonical_json_bytes(
                        arm_slice(export, arm_id)
                    )
                    expected[f"arms/{arm_id}/delta.json"] = canonical_json_bytes(
                        arm_delta(export, arm_id)
                    )
                    expected[f"arms/{arm_id}/grades.json"] = canonical_json_bytes(
                        arm_grades(grades_doc, arm_id)
                    )
            except Exception as exc:
                slice_detail = f"slices cannot be re-derived: {exc}"
                expected = {}
            if slice_detail is None:
                on_disk_arms = {
                    relpath for relpath in on_disk if relpath.startswith("arms/")
                }
                if on_disk_arms != set(expected):
                    difference = sorted(
                        on_disk_arms.symmetric_difference(expected)
                    )
                    slice_detail = (
                        f"{difference[0]}: slice set does not match the export"
                    )
                else:
                    for relpath in sorted(expected):
                        if (root / relpath).read_bytes() != expected[relpath]:
                            slice_detail = (
                                f"{relpath}: does not match its re-derivation "
                                "from export.json + grades.json"
                            )
                            break
    checks.append(_check("slices", slice_detail is None, slice_detail))

    # 6. Materials: every ticket ref resolves inside the pack and is listed.
    if not manifest.get("materials_included"):
        checks.append(_check("materials", True, "materials not included in pack"))
    elif export is None:
        checks.append(
            _check("materials", False, "export.json: unreadable, refs unknown")
        )
    else:
        material_detail = None
        for arm_id, ref in sorted(_arm_refs(export).items()):
            relpath = f"materials/{ref}"
            if relpath not in files_table or not (root / relpath).is_file():
                material_detail = (
                    f"{relpath}: arm {arm_id!r}'s delta ref is not in the pack"
                )
                break
        checks.append(_check("materials", material_detail is None, material_detail))

    return _report(root, checks)
