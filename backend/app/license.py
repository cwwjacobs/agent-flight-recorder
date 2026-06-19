"""Local feature flags — what's on by default vs. opt-in.

AFR is fully free and open source (MIT). Nothing here is gated behind payment
or a license key. Most of the product is always on. A small set of advanced /
experimental features are off by default and enabled with a single local flag:

    AFR_EXPERIMENTAL_FEATURES_ENABLED=true

Why gate them at all? Some are genuinely experimental, and the advanced replay
modes can execute real, side-effecting tools during replay — keeping them
opt-in avoids surprising side effects on a fresh install. This is a safety/UX
default, not a paywall.

  STANDARD (always on)
      local recorder, SDK, CLI, timeline UI, checkpoints,
      state-at-checkpoint, replay in safe modes (dry_run / mock_tools),
      always-on default key redaction (safety is never gated)

  ADVANCED / EXPERIMENTAL (opt-in)
      JSON state diff viewer, forked replay, full replay policy modes
      (allow_safe_tools / allow_side_effects), custom redactor hooks,
      run tags & notes, MCP-shaped HTTP prototype

The whole gate lives in this one module, so a deployment that wants everything
on just sets the flag.
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException

# Deprecated alias for AFR_EXPERIMENTAL_FEATURES_ENABLED. Kept so existing
# setups keep working; prefer the new name.
_DEPRECATED_ENV = "AFR_PREMIUM_ENABLED"
_ENV = "AFR_EXPERIMENTAL_FEATURES_ENABLED"

EXPERIMENTAL_FEATURES = {
    "state_diff": "JSON state diff viewer",
    "forked_replay": "fork a new run from any checkpoint",
    "replay_policies": "allow_safe_tools / allow_side_effects replay modes",
    "custom_redactors": "custom redaction hooks",
    "tags_notes": "run tags and notes",
    "mcp": "MCP-shaped HTTP prototype",
}

STANDARD_FEATURES = {
    "recorder": "event recording (SDK + API)",
    "timeline": "timeline UI and CLI",
    "checkpoints": "checkpoints and state-at-checkpoint",
    "replay_safe": "replay in dry_run / mock_tools modes",
    "default_redaction": "built-in secret-key redaction",
}

_TRUTHY = ("1", "true", "yes", "on")


def experimental_enabled() -> bool:
    """True when advanced/experimental features are switched on locally."""
    raw = os.environ.get(_ENV)
    if raw is None or not raw.strip():
        raw = os.environ.get(_DEPRECATED_ENV, "")  # deprecated back-compat alias
    return raw.strip().lower() in _TRUTHY


def feature_info() -> dict:
    """Feature availability snapshot (clients use it to adapt the UI)."""
    enabled = experimental_enabled()
    return {
        "experimental_enabled": enabled,
        "features": {
            **{k: True for k in STANDARD_FEATURES},
            **{k: enabled for k in EXPERIMENTAL_FEATURES},
        },
        "hint": (
            None
            if enabled
            else f"Set {_ENV}=true to enable advanced/experimental features "
            "(local flag — no payment or license key)."
        ),
    }


class FeatureDisabled(HTTPException):
    """Raised when an opt-in experimental feature is used while it is off."""

    def __init__(self, feature: str):
        super().__init__(
            status_code=403,
            detail={
                "error": "experimental_feature_disabled",
                "feature": feature,
                "description": EXPERIMENTAL_FEATURES.get(feature, feature),
                "hint": f"Set {_ENV}=true to enable this feature "
                "(local flag — no payment or license key).",
            },
        )


def require_experimental(feature: str) -> None:
    if not experimental_enabled():
        raise FeatureDisabled(feature)


def experimental_feature(feature: str):
    """FastAPI dependency: `dependencies=[experimental_feature("forked_replay")]`."""

    def dep() -> None:
        require_experimental(feature)

    return Depends(dep)
