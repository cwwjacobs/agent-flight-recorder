"""Custom redactor hooks (premium) + the single apply_redaction entry point.

A redactor is `Callable[[dict], dict]` — it receives a payload (already passed
through default redaction) and returns a scrubbed copy. Embedders register
them at startup:

    from app.redaction import register_redactor

    @register_redactor
    def drop_pii(payload: dict) -> dict:
        ...

Custom redactors only run when premium is enabled; the defaults always run
(unless AFR_REDACTION_ENABLED=false) because shipping secrets to disk is not
a feature tier.
"""

from __future__ import annotations

from typing import Any, Callable

from app.license import is_premium
from app.redaction.default import default_redact, redaction_enabled

Redactor = Callable[[dict], dict]

_redactors: list[Redactor] = []


def register_redactor(fn: Redactor) -> Redactor:
    _redactors.append(fn)
    return fn


def clear_redactors() -> None:
    _redactors.clear()


def apply_redaction(payload: Any) -> Any:
    if not redaction_enabled():
        return payload
    scrubbed = default_redact(payload)
    if _redactors and is_premium() and isinstance(scrubbed, dict):
        for redactor in _redactors:
            scrubbed = redactor(scrubbed)
    return scrubbed
