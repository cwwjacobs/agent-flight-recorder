# Quarantined MVP Snapshot

This directory is a preserved copy of the earlier MVP implementation.

It is retained for evidence, historical comparison, and recovery reference. It is not part of the active runtime, active Docker image, or active CI build path during containment review.

## Containment status

- Do not treat this directory as the current release surface.
- Do not run dependency installation from this directory during review.
- Keep the files available for diff, provenance, and audit.
- Prefer the repository root implementation for active development.

## Reason

The snapshot contains a full duplicated backend, SDK, CLI, UI, tests, docs, and package lock. That is useful for preservation, but it also expands the dependency and review surface. The snapshot should remain inert until explicitly re-audited.

## Current read

No wallet, miner, or crypto-currency indicators were found in the pasted local scan. External Google Fonts loading was removed from the preserved UI shell as a localhost-first privacy containment step.
