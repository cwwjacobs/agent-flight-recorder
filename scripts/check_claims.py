#!/usr/bin/env python3
"""Fail fast on high-risk public-copy drift.

This is not a semantic proof system. It is a small, dependency-free guardrail
for the highest-risk AFR overclaims that previously appeared in public docs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PUBLIC_DOCS = [
    ROOT / "README.md",
    ROOT / "docs" / "quickstart.md",
    ROOT / "docs" / "replay.md",
]

REQUIRED_SUBSTRINGS = {
    ROOT / "README.md": [
        "observable boundary",
        "does not expose",
        "Replay is deliberately disabled by default",
        "It does not execute user code",
        "best-effort",
    ],
    ROOT / "docs" / "replay.md": [
        "Replay is disabled by default",
        "AFR_REPLAY_ENABLED=true",
        "The server never runs your code",
        "Use the helpers",
    ],
}

# phrase, reason, allowed_context_regex
BANNED_PHRASES = [
    (
        "black box infrastructure",
        "Implies hidden/internal model observability. Use local-first run recorder language.",
        None,
    ),
    (
        "actual event trail",
        "Use recorded event trail/timeline; AFR only knows what was recorded.",
        None,
    ),
    (
        "exact event timeline",
        "Use recorded event timeline; exactness is too broad for unrecorded events.",
        None,
    ),
    (
        "safely replay",
        "Replay safety depends on the handler using SDK helpers.",
        re.compile(r"does not|not claim|avoid|without nearby boundary", re.I),
    ),
    (
        "safe replay",
        "Replay safety depends on the handler using SDK helpers.",
        re.compile(r"does not|not claim|avoid|without nearby boundary", re.I),
    ),
    (
        "without repeating real-world side effects",
        "Too absolute. Use mocked or gated tool execution plus handler boundary.",
        None,
    ),
    (
        "deterministic state reconstruction",
        "Too broad unless limited to recorded state_snapshot events.",
        re.compile(r"avoid|unless|recorded `state_snapshot`|limited to recorded", re.I),
    ),
    (
        "trust infrastructure",
        "Too broad for the current baseline. Use specific local recorder language.",
        None,
    ),
]

RISKY_REGEXES = [
    (
        re.compile(r"\breconstruct(?:s|ed|ing)? state\b", re.I),
        "Prefer reconstruct recorded state unless explicitly scoped.",
        re.compile(r"recorded state|state_snapshot|not full agent state|unless those states were recorded", re.I),
    ),
    (
        re.compile(r"\bredaction\b", re.I),
        "Redaction language must say best-effort nearby.",
        re.compile(r"best-effort", re.I),
    ),
]

STRUCTURAL_CHECKS = [
    (
        ROOT / "Dockerfile",
        ["AFR_UI_DIST=/app/ui-dist", "0.0.0.0", "COPY --from=ui /ui/dist /app/ui-dist"],
    ),
    (
        ROOT / "docker-compose.yml",
        ["127.0.0.1:8700:8700", "AFR_REPLAY_ENABLED"],
    ),
    (
        ROOT / "docs" / "claim-contract.md",
        ["AFR-C-001", "Red phrases", "Review checklist"],
    ),
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _line_window(lines: list[str], index: int, radius: int = 2) -> str:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    return "\n".join(lines[start:end])


def check_required(errors: list[str]) -> None:
    for path, needles in REQUIRED_SUBSTRINGS.items():
        text = _read(path)
        if not text:
            errors.append(f"missing required doc: {path.relative_to(ROOT)}")
            continue
        for needle in needles:
            if needle not in text:
                errors.append(f"{path.relative_to(ROOT)} missing required boundary text: {needle!r}")


def check_banned_phrases(errors: list[str]) -> None:
    for path in PUBLIC_DOCS + [ROOT / "docs" / "claim-contract.md"]:
        text = _read(path)
        if not text:
            errors.append(f"missing public doc: {path.relative_to(ROOT)}")
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            for phrase, reason, allowed_context in BANNED_PHRASES:
                if phrase not in lower:
                    continue
                if allowed_context and allowed_context.search(line):
                    continue
                errors.append(
                    f"{path.relative_to(ROOT)}:{lineno}: banned/high-risk phrase {phrase!r}. {reason}"
                )


def check_risky_regexes(errors: list[str]) -> None:
    for path in PUBLIC_DOCS:
        text = _read(path)
        if not text:
            continue
        lines = text.splitlines()
        for index, line in enumerate(lines):
            for pattern, reason, allowed_context in RISKY_REGEXES:
                if not pattern.search(line):
                    continue
                window = _line_window(lines, index)
                if allowed_context.search(window):
                    continue
                errors.append(
                    f"{path.relative_to(ROOT)}:{index + 1}: risky wording. {reason}"
                )


def check_structural_claims(errors: list[str]) -> None:
    for path, needles in STRUCTURAL_CHECKS:
        text = _read(path)
        if not text:
            errors.append(f"missing structural evidence file: {path.relative_to(ROOT)}")
            continue
        for needle in needles:
            if needle not in text:
                errors.append(f"{path.relative_to(ROOT)} missing evidence text: {needle!r}")


def main() -> int:
    errors: list[str] = []
    check_required(errors)
    check_banned_phrases(errors)
    check_risky_regexes(errors)
    check_structural_claims(errors)

    if errors:
        print("Claim sanity check failed:\n", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Claim sanity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
