"""Default key-based redaction."""

from __future__ import annotations

import os
from typing import Any

REDACTED_MARKER = "[REDACTED]"

# Substring match, case-insensitive, against each dict key. "api_key" catches
# OPENAI_API_KEY, anthropic_api_key, apiKeyHeader, ... Deliberately NOT plain
# "token": that would eat usage telemetry (prompt_tokens, total_tokens,
# token_count). Secret-shaped token keys are matched explicitly instead.
DEFAULT_REDACT_KEYS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "passwd",
    "secret",
    "access_token",
    "refresh_token",
    "id_token",
    "session_token",
    "auth_token",
    "bearer_token",
    "api_token",
    "private_key",
    "credential",
    "session_id",
    "cookie",
)

# Exact match (case-insensitive): keys whose bare word would over-match as a
# substring but are secrets when they appear verbatim.
DEFAULT_REDACT_EXACT: tuple[str, ...] = (
    "token",
    "bearer",
    "auth",
    "jwt",
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
    return lowered in DEFAULT_REDACT_EXACT or any(needle in lowered for needle in needles)


def default_redact(value: Any, needles: tuple[str, ...] | None = None) -> Any:
    """Recursively replace values under sensitive keys with the marker."""
    if needles is None:
        needles = _redact_keys()
    if isinstance(value, dict):
        return {
            k: REDACTED_MARKER if _key_is_sensitive(str(k), needles) else default_redact(v, needles)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [default_redact(item, needles) for item in value]
    return value
