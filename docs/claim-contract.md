# Public claim contract

This document keeps AFR's public language tied to code, docs, or explicit limits. It is not marketing copy. It is a reviewer-facing guardrail for README, docs, release notes, marketplace blurbs, and contest submissions.

## Rule

Every public claim should pass this test:

> Can a reviewer verify this from the repository without trusting our intent?

If the answer is no, the claim should be narrowed, moved to roadmap language, or removed.

## Claim record shape

Use this shape when adding a new high-value claim:

```text
CLAIM-ID:
Claim:
Scope:
Evidence:
Boundary:
Public wording:
```

- **Claim**: what we want to say.
- **Scope**: where it is true.
- **Evidence**: code, test, doc, workflow, receipt, or demo path.
- **Boundary**: what it does not prove.
- **Public wording**: the safe version allowed in user-facing text.

## Current allowed public claims

### AFR-C-001: local-first run recorder

Claim: AFR is a local-first run recorder for tool-using AI agents.

Scope: The default backend and Docker compose paths bind to loopback, use local SQLite storage, and record observable run events through the SDK/API/CLI paths.

Evidence:

- `README.md`
- `docker-compose.yml`
- `backend/app/config.py`
- `backend/app/storage/repo.py`
- `sdk/afr/wrappers.py`

Boundary: This does not make AFR an enterprise security product, a sandbox, or a hosted observability platform.

Public wording: "Local-first recorder for observable tool-using agent runs."

### AFR-C-002: observable boundary capture

Claim: AFR records observable agent run boundary events.

Scope: AFR can record model calls, tool calls, tool results, state snapshots, checkpoints, errors, and replay requests when the SDK/API/CLI/adapter path records them.

Evidence:

- `README.md`
- `backend/app/api/`
- `backend/app/engine/events.py`
- `backend/app/engine/checkpoints.py`
- `sdk/afr/wrappers.py`
- `sdk/afr/hooks.py`

Boundary: AFR does not expose hidden model reasoning, true model intent, neural activations, or unrecorded process state.

Public wording: "AFR records model calls, tool calls, tool results, state snapshots, checkpoints, errors, and replay requests when those events are recorded through the SDK, API, CLI, or adapter path in use."

### AFR-C-003: append-only recorded event timeline

Claim: AFR stores recorded events in an append-only event timeline.

Scope: Event rows are inserted with sequence numbers through repository append paths; there is no normal update/delete path for event rows in the repository layer.

Evidence:

- `backend/app/engine/events.py`
- `backend/app/storage/repo.py`
- `docs/data-model.md`

Boundary: Runs and metadata can still have update paths. Append-only applies to recorded events, not every database table.

Public wording: "append-only recorded event timelines."

### AFR-C-004: recorded state reconstruction

Claim: AFR can reconstruct recorded state as of a checkpoint.

Scope: State reconstruction folds recorded `state_snapshot` events and checkpoint state copies.

Evidence:

- `backend/app/engine/state.py`
- `backend/app/engine/checkpoints.py`
- `backend/app/replay/service.py`
- `docs/replay.md`

Boundary: This is not full agent state, model state, browser state, external-world state, or hidden memory unless those states were recorded.

Public wording: "recorded state snapshots and checkpoint metadata" or "reconstructs recorded state."

Avoid: "deterministic state reconstruction" unless the surrounding sentence says it is limited to recorded `state_snapshot` events.

### AFR-C-005: replay tickets and helper-enforced replay behavior

Claim: AFR can prepare replay tickets with a per-tool plan and SDK helpers for mock/skip/block/allow decisions.

Scope: The backend prepares replay tickets; the SDK helpers can honor the plan; user code execution happens in the resume handler.

Evidence:

- `backend/app/replay/service.py`
- `backend/app/replay/policies.py`
- `sdk/afr/hooks.py`
- `docs/replay.md`

Boundary: The server does not execute user code. A resume handler can bypass protection if it ignores SDK helpers and calls tools directly.

Public wording: "prepare a replay ticket using mocked or gated tool execution" or "side-effect-aware replay helpers."

Avoid: "safe replay" or "safely replay" without nearby boundary language.

### AFR-C-006: Docker backend plus UI path

Claim: Docker can serve the backend and built UI on `http://127.0.0.1:8700`.

Scope: The Docker image builds the UI, copies `ui/dist`, sets `AFR_UI_DIST`, and binds uvicorn to `0.0.0.0` inside the container while compose publishes host loopback only.

Evidence:

- `Dockerfile`
- `docker-compose.yml`
- `backend/app/main.py`

Boundary: This says the container path is wired correctly. It does not replace actual Docker smoke validation.

Public wording: "Docker builds the web UI and serves it alongside the API on `http://127.0.0.1:8700`."

## Red phrases

These phrases should not appear in public docs unless they are inside a denial, warning, or explicit boundary section:

- "black box infrastructure"
- "actual event trail"
- "exact event timeline"
- "safe replay"
- "safely replay"
- "without repeating real-world side effects"
- "deterministic state reconstruction"
- "trust infrastructure"
- "privacy-preserving" without a best-effort/privacy-boundary qualifier

## Orange phrases

These phrases are allowed only with tight scope language nearby:

- "reconstruct state" -> use "reconstruct recorded state"
- "replay" -> mention replay flag and handler boundary when explaining behavior
- "redaction" -> mention best-effort
- "security" -> say localhost-first and token-gated, not secure-by-default outside loopback
- "integration" -> name the exact integration path that exists

## Review checklist

Before merging public copy changes, check:

1. The claim is backed by a code/doc path.
2. The claim says "recorded" when talking about timeline or state.
3. Replay language mentions the server/client split or SDK helper boundary.
4. Redaction language says best-effort.
5. Docker/UI claims match the Dockerfile and compose file.
6. New aspirational work is labelled roadmap, planned, or future.

## Automation

`scripts/check_claims.py` enforces the highest-risk wording checks. It is intentionally small and conservative. It does not prove every claim, but it catches public-copy drift early.
