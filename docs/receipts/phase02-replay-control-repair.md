# Phase 02 replay-control repair receipt

Date: 2026-06-18  
Baseline commit: `b74787fc0a858cfdb8cd2ad30ff611ce30282fb6`  
Stage 3 decision: **REVIEW_REQUIRED**

## Issues fixed

- The SDK now treats the replay ticket as an authorization boundary. A
  non-dry-run handler can be resolved and invoked only when `ticket.status` is
  exactly `ready`.
- `disabled`, `limit_exhausted`, unknown, missing, non-string, and malformed
  ticket statuses fail closed before handler invocation.
- Ticket rejections write a durable `replay_rejected` event when a client or
  active-run event context exists.
- Replay planning and execution now have finite defaults: 10,000 recorded tool
  events, 100 SDK tool steps, and 30 seconds of SDK handler wait time. Invalid
  and non-positive settings fail closed.
- SDK handler runs write durable `replay_started`, sanitized `replay_action`,
  and `replay_completed`, `replay_failed`, or `replay_limit_exhausted` events
  where applicable.
- Replay audit events include actor, checkpoint, mode, correlation, and parent
  metadata where the backend ticket and created events make those values
  available. Handler and tool results are represented by type and digest in
  lifecycle events rather than copied verbatim.
- `backend/requirements.txt` is consumed as a pip constraint by Docker, CI, and
  `make install`. Direct dependencies and the AnyIO compatibility constraint
  are exact-version pinned.
- Replay-control, lifecycle-audit, finite-bound, and dependency-consumption
  tests were added.

## Files changed

- `.github/workflows/ci.yml`
- `Dockerfile`
- `Makefile`
- `backend/app/config.py`
- `backend/app/schemas/models.py`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/tests/conftest.py`
- `backend/tests/test_dependency_integrity.py`
- `backend/tests/test_sdk_replay_controls.py`
- `docs/dependency-integrity.md`
- `docs/quickstart.md`
- `docs/replay.md`
- `docs/receipts/phase02-replay-control-repair.md`
- `sdk/afr/hooks.py`
- `sdk/afr/types.py`

## Tests run

- `make test PY=/tmp/afr-py312/bin/python`
  - PASS: 119 tests passed in 16.80 seconds.
- `/tmp/afr-py312/bin/python -m pytest backend/tests/test_sdk_replay_controls.py backend/tests/test_replay_controls.py backend/tests/test_dependency_integrity.py -q`
  - PASS: 26 tests passed in 5.68 seconds.
- `PYTHON=/tmp/afr-py312/bin/python AFR_BIN=/tmp/afr-py312/bin/afr scripts/smoke-kimi-package.sh`
  - PASS.
- `.venv/bin/python -m pytest backend/tests/test_dependency_integrity.py -q`
  - PASS: 2 tests passed in 0.03 seconds.
- `.venv/bin/python -m py_compile sdk/afr/hooks.py sdk/afr/types.py backend/app/config.py backend/app/schemas/models.py backend/tests/test_sdk_replay_controls.py backend/tests/test_dependency_integrity.py`
  - PASS.
- `git diff --check`
  - PASS.

The required test commands used a clean temporary Python 3.12 environment
installed from `backend/requirements.txt`. The checkout's pre-existing Python
3.13 environment and user-site Python 3.12 packages deadlocked in FastAPI's
threaded test portal under the restricted execution sandbox; the clean runtime
was run outside that restriction for verification.

## Verification result

The primary replay-control bypass is fixed and covered by explicit negative
and positive SDK tests. The code repair findings listed above are fixed and the
full Python suite plus the Kimi package smoke pass. Stage 3 remains
`REVIEW_REQUIRED` because the evidence-limited risks below were not converted
into locally provable claims.

## Remaining risks

- **Secrets coverage — REVIEW_REQUIRED:** the working tree has existing scoped
  review documentation, but full Git history, all refs, built images, packages,
  deployment configuration, and runtime secret stores were not scanned in this
  repair. This receipt does not claim repository-wide or artifact-wide secrets
  coverage.
- **Dependency integrity — REVIEW_REQUIRED:** the constraint file has exact
  versions but no artifact hashes and is not a complete transitive lock. Docker
  base images remain patch-tag pinned, not digest pinned. No dependency hashes
  or image digests were invented. Docker and hosted CI configuration were
  statically tested but were not executed locally.
- **Timeout cancellation — REVIEW_REQUIRED:** Python cannot forcibly terminate
  an already-running handler thread. The SDK returns a finite timeout outcome
  and stops waiting, but a non-cooperative handler may continue in its worker
  thread. Strong isolation requires running replay handlers in a separately
  terminable process or sandbox.
- **Handler trust boundary — REVIEW_REQUIRED:** lifecycle and action audit
  events are durable when handlers use `ReplayContext.call_tool`, but arbitrary
  user-supplied handler code can call external systems directly and bypass that
  helper. End-to-end containment of untrusted handlers is not locally proven.
- **Durability scope — REVIEW_REQUIRED:** durable rejection and lifecycle
  events require an available backend client or active run context. If that
  persistence path itself is unavailable, the SDK cannot durably record the
  event.
