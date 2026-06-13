"""Default key-based redaction (+ value-level secret scrubbing)."""

from __future__ import annotations

import os
import re
from typing import Any

REDACTED_MARKER = "[REDACTED]"

# Substring match, case-insensitive, against each dict key. "api_key" catches
# OPENAI_API_KEY, anthropic_api_key, apiKeyHeader, ...
DEFAULT_REDACT_KEYS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "private_key",
    "credential",
    "session_id",
    "cookie",
)

# Value-level secret patterns — catch secrets embedded in free-text values
# (model prompts, tool results, tracebacks) that key-name matching misses.
# Conservative and anchored to keep false positives low.
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
        re.S,
    ),
    re.compile(r"\bsk-(?:ant-|proj-|live-)?[A-Za-z0-9]{16,}\b"),       # OpenAI / Anthropic
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),                      # AWS access key id
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),                     # GitHub token
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),                   # GitHub fine-grained PAT
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),                   # Slack token
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),                         # Google API key
    re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
    ),                                                                 # JWT
)

# Patterns where only the secret is replaced, keeping the surrounding context.
_SECRET_GROUP_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1" + REDACTED_MARKER),
    (
        re.compile(r"([a-z][a-z0-9+.\-]*://[^/\s:@]+:)[^/\s:@]+(@)"),
        r"\1" + REDACTED_MARKER + r"\2",
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd|access[_-]?key)"
            r"(\s*[:=]\s*['\"]?)[A-Za-z0-9._\-]{8,}"
        ),
        r"\1\2" + REDACTED_MARKER,
    ),
)


def redaction_enabled() -> bool:
    return os.environ.get("AFR_REDACTION_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _redact_keys() -> tuple[str, ...]:
    extra = os.environ.get("AFR_REDACT_KEYS", "")
    extras = tuple(k.strip().lower() for k in extra.split(",") if k.strip())
    return DEFAULT_REDACT_KEYS + extras


def _key_is_sensitive(key: str, needles: tuple[str, ...]) -> bool:
    lowered = key.lower()
    return any(needle in lowered for needle in needles)


def _redact_text(text: str) -> str:
    """Redact secret-shaped substrings inside a free-text string value."""
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub(REDACTED_MARKER, text)
    for pattern, repl in _SECRET_GROUP_SUBS:
        text = pattern.sub(repl, text)
    return text


def default_redact(value: Any, needles: tuple[str, ...] | None = None) -> Any:
    """Recursively redact values under sensitive keys, and secret-shaped
    substrings inside any free-text string value."""
    if needles is None:
        needles = _redact_keys()
    if isinstance(value, dict):
        return {
            k: REDACTED_MARKER if _key_is_sensitive(str(k), needles) else default_redact(v, needles)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [default_redact(item, needles) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value
