# AGENTS.md

Repository instructions for AI coding agents working on Agent Flight Recorder.

## Project Summary

Agent Flight Recorder (AFR) is a local-first run recorder for tool-using AI agents. It records the observable boundary of an agent run: model calls, tool calls, tool results, state snapshots, checkpoints, errors, and replay requests.

AFR does not claim to recover private model reasoning, hidden chain-of-thought, neural state, or true internal intent. Preserve that boundary in docs and code.

## Main Commands

```bash
make install      # create venv and install backend, sdk, cli, and test deps
make test         # run backend/tests via pytest
make serve        # run backend API on http://127.0.0.1:8700
make smoke        # smoke test against running backend
make demo         # record toy agent run via SDK
make demo-docker  # seed demo incident over HTTP
```

## Agent Operating Rules

1. Read this file and README.md before editing.
2. Prefer small, bounded diffs.
3. Preserve AFR's truth boundary: observable execution evidence, not private model internals.
4. Do not broaden security, enterprise, sandbox, or interpretability claims beyond what the repo implements.
5. Do not delete or weaken tests to make a run pass.
6. Do not add dependencies without explaining why.
7. Keep replay gated and explicit. Replay is disabled by default unless configured.
8. Run `make test` for backend-affecting changes when practical.
9. Summarize changed files, verification, and known limitations.

## Safe Change Boundaries

Allowed by default:

- documentation clarifications
- small tests
- small backend/SDK/CLI fixes tied to the requested task
- local examples or receipts

Needs review:

- replay behavior changes
- database/schema changes
- Docker or CI changes
- dependency or lockfile changes
- security-sensitive behavior
- claims about what AFR can observe or guarantee
- changes that affect public API, SDK, or CLI behavior

## Final Response Format

```text
Summary:
-

Changed files:
-

Verification:
-

Risks / notes:
-
```

## Frontend Boundary

This project does not use React, Vite, Next, Vue, Svelte, or npm-based application frameworks for core functionality.

AFR is CLI-first and local-first. User-facing surfaces may be CLI commands, terminal TUI, markdown reports, JSON / JSONL exports, or plain static HTML generated from trusted local data.

No frontend dependency graph may become required for core AFR functionality.

The legacy UI path is not part of AFR v0.2. AFR v0.2 is the CLI Visibility Cut.

Legacy UI work must be explicitly requested. Do not use `make build-ui`, npm, or frontend framework tooling for core AFR changes.
