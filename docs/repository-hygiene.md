# Repository Hygiene Checklist

This repository uses a solo-maintainer workflow with protected `main` and pull-request based changes.

## Baseline protections

- Default branch is protected.
- Pull requests are required before changes reach `main`.
- Force pushes are disabled.
- Branch deletion is disabled.
- Administrator enforcement is enabled where practical.

## Release hygiene

Before a public release or major merge:

- Run relevant tests and smoke checks.
- Confirm generated artifacts are excluded unless intentionally published.
- Prefer a release tag for stable milestones.
- Include receipts or verification notes for sensitive changes.

## Public presentation

Recommended public-facing assets:

- Clear README positioning
- LICENSE
- SECURITY.md
- CONTRIBUTING.md
- Release tags
- Repository description and topics
- Pinned profile repositories

## Agent tooling notes

For agent capture, replay, trace, or package-export features:

- Document trust boundaries.
- Document failure behavior.
- Treat raw traces as private by default.
- Prefer sanitized share packages.
- Include smoke tests with placeholder redaction checks where relevant.
