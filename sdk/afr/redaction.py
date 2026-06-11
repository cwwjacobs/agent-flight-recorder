"""Client-side redaction (premium feature, mirrors backend behaviour).

The backend always applies default key redaction at ingest. Register a
client-side redactor when a value must never even leave your process:

    import afr

    @afr.redaction.register_redactor
    def scrub(payload: dict) -> dict:
        payload.pop("internal_trace", None)
        return payload

    afr.redaction.enable_default_redaction()   # optional: scrub known keys
                                               # client-side too

Redactors run on every payload the SDK sends (events, checkpoint state,
run metadata).
"""

from __future__ import annotations

from typing import Any, Callable

REDACTED_MARKER = "[REDACTED]"

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

Redactor = Callable[[dict], dict]

_redactors: list[Redactor] = []
_default_enabled = False


def register_redactor(fn: Redactor) -> Redactor:
    _redactors.append(fn)
    return fn


def clear_redactors() -> None:
    global _default_enabled
    _redactors.clear()
    _default_enabled = False


def enable_default_redaction(enabled: bool = True) -> None:
    global _default_enabled
    _default_enabled = enabled


def default_redact(value: Any, needles: tuple[str, ...] = DEFAULT_REDACT_KEYS) -> Any:
    if isinstance(value, dict):
        return {
            k: REDACTED_MARKER if any(n in str(k).lower() for n in needles) else default_redact(v, needles)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [default_redact(item, needles) for item in value]
    return value


def apply(payload: Any) -> Any:
    """Run the configured client-side redaction pipeline over a payload."""
    if _default_enabled:
        payload = default_redact(payload)
    if _redactors and isinstance(payload, dict):
        for redactor in _redactors:
            payload = redactor(payload)
    return payload
