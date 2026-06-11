"""License boundary — PLACEHOLDER, no real billing.

The split:

  FREE     local recorder, SDK, CLI, basic timeline UI, checkpoints,
           state-at-checkpoint, replay in safe modes (dry_run / mock_tools),
           always-on default key redaction (safety is not a paywall)

  PREMIUM  JSON state diff viewer, forked replay, full replay policy modes
           (allow_safe_tools / allow_side_effects), custom redactor hooks,
           run tags & notes, MCP server stub

Toggle with:  AFR_PREMIUM_ENABLED=true

Replace `is_premium()` with a real entitlement check (license key, billing
API, ...) when payments exist; everything else gates through this module.
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException

PREMIUM_FEATURES = {
    "state_diff": "JSON state diff viewer",
    "forked_replay": "fork a new run from any checkpoint",
    "replay_policies": "allow_safe_tools / allow_side_effects replay modes",
    "custom_redactors": "custom redaction hooks",
    "tags_notes": "run tags and notes",
    "mcp": "MCP server stub",
}

FREE_FEATURES = {
    "recorder": "event recording (SDK + API)",
    "timeline": "timeline UI and CLI",
    "checkpoints": "checkpoints and state-at-checkpoint",
    "replay_safe": "replay in dry_run / mock_tools modes",
    "default_redaction": "built-in secret-key redaction",
}


def is_premium() -> bool:
    return os.environ.get("AFR_PREMIUM_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def license_info() -> dict:
    premium = is_premium()
    return {
        "premium": premium,
        "plan": "premium" if premium else "free",
        "features": {
            **{k: True for k in FREE_FEATURES},
            **{k: premium for k in PREMIUM_FEATURES},
        },
        "hint": None if premium else "Set AFR_PREMIUM_ENABLED=true to enable premium features.",
    }


class PremiumRequired(HTTPException):
    def __init__(self, feature: str):
        super().__init__(
            status_code=402,
            detail={
                "error": "premium_required",
                "feature": feature,
                "description": PREMIUM_FEATURES.get(feature, feature),
                "hint": "Set AFR_PREMIUM_ENABLED=true (license placeholder — no real billing).",
            },
        )


def ensure_premium(feature: str) -> None:
    if not is_premium():
        raise PremiumRequired(feature)


def premium_feature(feature: str):
    """FastAPI dependency: `dependencies=[premium_feature("forked_replay")]`."""

    def dep() -> None:
        ensure_premium(feature)

    return Depends(dep)
