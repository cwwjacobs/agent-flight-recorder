# Agent Flight Recorder

[![CI](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml/badge.svg)](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**AI agent observability, replay debugging, and checkpoint inspection for LLM apps.**

Agent Flight Recorder (AFR) is a localhost-first black box for Python agents. It records model calls, tool calls, state snapshots, checkpoints, logs, and errors into a structured SQLite timeline so failures can be inspected and replayed without losing the state that caused them.

```text
1. Record        — model calls, tools, state snapshots, checkpoints
2. Inspect       — walk the exact event timeline and state at failure time
3. Replay safely — resume from a checkpoint with side-effecting tools mocked or gated
```

## Why AFR exists

AI agent failures are hard to debug because the decisive state is often gone by the time the failure is noticed. Reproducing the issue can require rerunning model calls, repeating tool calls, and risking duplicated side effects.

AFR keeps the evidence:

- append-only event timelines
- deterministic state reconstruction
- checkpoint inspection
- replay tickets
- side-effect-aware replay policies
- CLI and web UI inspection paths
- SQLite-first local storage
- best-effort redaction at ingest

## Quickstart

```bash
docker compose up --build     # backend + UI on http://localhost:8700
make demo-docker              # seed the checkout-agent-payment-timeout demo incident
open http://localhost:8700
```

Without Docker:

```bash
make install
make serve
make build-ui
make demo
afr doctor
```

## Record your agent

```python
import afr

@afr.record_tool_call
def search_flights(destination: str, budget_usd: int) -> dict:
    ...

@afr.record_model_call(model="gpt-x", provider="openai")
def ask_llm(prompt: str) -> str:
    ...

with afr.start_run("trip-planner", metadata={"env": "dev"}):
    plan = ask_llm("plan a trip to Tokyo")
    flights = search_flights("Tokyo", 900)
    afr.log_state({"booked": {"flight": flights}}, mode="merge")
    afr.checkpoint("after-flights")
```

## Replay from a checkpoint

```python
import afr

@afr.register_resume_handler
def resume(ctx: afr.ReplayContext):
    agent = MyAgent.from_state(ctx.state)
    return agent.continue_run()

afr.replay(run_id, checkpoint_id, mode="mock_tools")
```

The server reconstructs state and prepares a replay plan. It does not execute user code. Your resume handler enforces the plan, including mock, skip, block, and allow decisions for tool calls.

## Integrations

| Stack | AFR attachment path |
| --- | --- |
| Plain Python | decorators + `with afr.start_run(...)` |
| LangChain / LangGraph | callback handler |
| Custom framework | HTTP API or SDK calls |

See:

- [docs/quickstart.md](docs/quickstart.md)
- [docs/sdk.md](docs/sdk.md)
- [docs/cli.md](docs/cli.md)
- [docs/api.md](docs/api.md)
- [docs/replay.md](docs/replay.md)
- [docs/data-model.md](docs/data-model.md)
- [docs/integrations.md](docs/integrations.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/mcp.md](docs/mcp.md)

## Security model

AFR is localhost-first. Recorded prompts, tool payloads, and state snapshots can contain sensitive information.

- The backend binds to `127.0.0.1` by default.
- CORS is restricted to local dev origins by default.
- Set `AFR_API_TOKEN=<token>` before exposing AFR outside loopback.
- Redaction runs at ingest and is best-effort, not a guarantee.
- Treat the SQLite database as sensitive at rest.

## Repository layout

```text
backend/   FastAPI app: API, replay engine, storage, schemas
sdk/       Python SDK: client, context, hooks, wrappers, integrations
cli/       afr CLI
ui/        Vite + React + TypeScript operator console
examples/  runnable offline demo agents
scripts/   demo and smoke helpers
docs/      quickstart, SDK, CLI, API, replay, data model, integrations
```

## Tests

```bash
make test
make smoke
```

## Release status

This repository is prepared for an OSS submission / release freeze. The current public license is MIT with Terminus Protocol attribution.

See:

- [LICENSE](LICENSE)
- [NOTICE](NOTICE)
- [SUBMISSION_NOTES.md](SUBMISSION_NOTES.md)
- [OPEN_SOURCE_FREEZE.md](OPEN_SOURCE_FREEZE.md)

## License

Agent Flight Recorder is released under the [MIT License](LICENSE).

Copyright (c) 2026 Terminus Protocol.
