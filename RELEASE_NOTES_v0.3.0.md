# Agent Flight Recorder v0.3.0

v0.3.0 is the audited source-available baseline. It moves current development to
PolyForm Noncommercial 1.0.0 and keeps prior release grants intact for the
versions they accompanied.

## Reliability

- Default demo seeding succeeds when replay is disabled and returns the actual
  disabled replay state.
- SDK and smoke traffic ignore ambient proxy configuration by default for the
  localhost-first deployment model.
- Run exports, regression-case generation, and UI event retrieval paginate
  through the complete event timeline.
- Model and tool decorators correctly await and record async functions.

## Dependency and build integrity

- AnyIO is pinned to 4.14.2 to address CVE-2026-63374 and CVE-2026-64847.
- The UI dependency tree has been refreshed and audits clean at release review
  time.
- CI audits and compiles the UI instead of skipping it.
- Python wheels include the current license text.

## License

Current v0.3.0 source is licensed under PolyForm Noncommercial 1.0.0 by Corey
Jacobs. Commercial licensing inquiries: `coresynth@gmail.com`.

See `docs/audit-2026-09-19.md` for the verification receipt and known
limitations.
