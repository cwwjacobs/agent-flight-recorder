# Repository Map

Agent-ready map for Agent Flight Recorder.

## Project Identity

- Repository: `cwwjacobs/agent-flight-recorder`
- Project: Agent Flight Recorder (AFR)
- Purpose: local-first run recorder for tool-using AI agents
- Main language: Python backend/SDK/CLI, JavaScript UI
- Default branch: `main`

## Main Paths

| Path | Purpose | Agent notes |
|---|---|---|
| `backend/` | AFR backend/API | Backend app and tests live here. |
| `backend/tests/` | Python tests | `make test` runs these tests. |
| `sdk/` | Python SDK | Preserve public API compatibility. |
| `cli/` | AFR CLI | CLI entry points and command behavior. |
| `ui/` | Optional web UI | Build with `make build-ui`. |
| `examples/` | Example agent runs/adapters | Good place for proof demos. |
| `scripts/` | Demo and smoke utilities | Used by demo/smoke commands. |
| `.github/` | CI and GitHub config | Review before changing. |

## Common Commands

| Command | Purpose |
|---|---|
| `make install` | Create venv and install backend, SDK, CLI, test deps. |
| `make test` | Run Python test suite. |
| `make serve` | Run backend on localhost. |
| `make build-ui` | Build UI for backend-served static assets. |
| `make smoke` | Run smoke test against running backend. |
| `make demo` | Record toy agent run via SDK. |
| `make demo-docker` | Seed demo incident over HTTP. |

## Agent-Sensitive Boundaries

Preserve these claims:

- AFR records observable execution evidence.
- AFR does not recover hidden model reasoning or true internal intent.
- Replay is explicit and gated.
- Redaction is best-effort, not a guarantee.
- Recorded prompts, tool payloads, and state snapshots may contain sensitive data.

## Suggested First Agent Task

```text
Read AGENTS.md, README.md, and repo-map.md.
Make one documentation-only improvement.
Run no broad rewrites.
Complete review-gate.md in the final response.
```
