# Agent Flight Recorder

[![CI](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml/badge.svg)](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Local-first run recorder for tool-using AI agents.**

Agent Flight Recorder (AFR) records the observable boundary of an agent run: model calls, tool calls, tool results, state snapshots, checkpoints, errors, and replay requests.

AFR does not expose a model's private reasoning, hidden chain-of-thought, or internal neural state. It records execution evidence available outside the model so an operator can inspect what happened, reconstruct recorded state, and test recovery paths with side effects mocked or gated.

```text
1. Record   - capture model calls, tool calls, state snapshots, checkpoints, and errors
2. Inspect  - review the event timeline and recorded state around a failure
3. Replay   - prepare a replay request using mocked or gated tool execution
```

## Why AFR exists

Tool-using agents can fail after prompts, tool calls, state updates, or external side effects have already happened. By the time the failure is noticed, the exact run context may be scattered across logs or gone.

AFR keeps a local record of the run boundary:

- append-only event timelines
- recorded state snapshots and checkpoint metadata
- checkpoint inspection
- replay tickets and replay plans
- side-effect-aware replay policies
- CLI inspection paths
- SQLite-first local storage
- best-effort redaction at ingest

## What AFR does

AFR is intended for local development, debugging, evaluation, and audit workflows. It helps answer practical questions:

- What did the agent receive?
- What did the model return?
- What tools were requested or executed?
- What state was recorded before the failure?
- Which checkpoint can be used to prepare a replay request?
- Which side-effecting tools should be mocked, skipped, blocked, or explicitly allowed?

The replay boundary is explicit. The backend reconstructs recorded state and prepares a replay plan. It does not execute user code. A user-provided resume handler decides how replay execution happens and should use the SDK helpers to honor mock, skip, block, and allow decisions.

## What AFR does not claim

AFR is not a model interpretability system. It does not recover true model intent, private reasoning, hidden chain-of-thought, neural activations, or training traces.

AFR is not an enterprise security product or sandbox by itself. Recorded prompts, tool payloads, and state snapshots can contain sensitive data. Redaction is best-effort, not a guarantee.

AFR is not a guarantee that every state change was captured. State reconstruction is limited to events and snapshots actually recorded by the SDK, CLI, API, or adapter path in use.

## Quickstart

Docker builds the web UI, serves it alongside the API on `http://127.0.0.1:8700`, and stores data in a local Docker volume:

```bash
docker compose up --build     # backend + UI on http://127.0.0.1:8700
make demo-docker              # seed the checkout-agent-payment-timeout demo incident
open http://127.0.0.1:8700
```

Without Docker (the backend, SDK, and CLI work on their own; the UI is optional):

```bash
make install
make serve                    # API on http://127.0.0.1:8700
make build-ui                 # optional: build the UI — the backend serves ui/dist
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

The server reconstructs recorded state and prepares a replay plan. It does not execute user code. The resume handler enforces the plan when it uses the SDK helpers, including mock, skip, block, and allow decisions for tool calls.

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
- [CODEX_REVIEW.md](CODEX_REVIEW.md)

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
ui/        React/Vite operator console source
examples/  runnable offline demo agents
scripts/   demo and smoke helpers
docs/      quickstart, SDK, CLI, API, replay, data model, integrations
```

## Tests

```bash
make test
make smoke
```

## Project status

AFR is a public OSS baseline maintained by Corey Jacobs / cwwjacobs. The project is MIT licensed with Terminus Protocol copyright and notice metadata preserved in the repository.

Current focus areas:

- hardening replay policy behavior
- expanding adapter coverage beyond the current Python and LangChain / LangGraph paths
- improving diff and checkpoint inspection flows
- preserving local-first privacy while making agent failures easier to reproduce safely

See:

- [LICENSE](LICENSE)
- [NOTICE](NOTICE)
- [OPEN_SOURCE_FREEZE.md](OPEN_SOURCE_FREEZE.md)
- [CODEX_REVIEW.md](CODEX_REVIEW.md)

## License

Agent Flight Recorder is released under the [MIT License](LICENSE).

Copyright (c) 2026 Terminus Protocol.
