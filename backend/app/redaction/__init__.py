"""Redaction: scrub secrets out of payloads before they touch the database.

Applied at ingest (events, checkpoint state, run metadata):

  1. default key-based redaction (always on; disable: AFR_REDACTION_ENABLED=false)
  2. custom redactor hooks (premium) registered via app.redaction.hooks

Redacted values become the literal string "[REDACTED]"; the UI renders that
marker as an explicit chip so a redacted field is never mistaken for data.
"""

from app.redaction.default import (  # noqa: F401
    REDACTED_MARKER,
    default_redact,
    redaction_enabled,
)
from app.redaction.hooks import apply_redaction, clear_redactors, register_redactor  # noqa: F401
