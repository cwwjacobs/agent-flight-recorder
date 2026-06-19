# Agent Flight Recorder

[![CI](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml/badge.svg)](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Open, localhost-first black box infrastructure for AI agents.**

Agent Flight Recorder (AFR) records what an autonomous agent did, preserves the state that led to a failure, and helps operators safely replay from a checkpoint without repeating real-world side effects.

As agents begin sending messages, calling APIs, changing records, and moving money, teams need more than observability. They need an accountability layer: a way to inspect the actual event trail, reconstruct the decisive state, and test a recovery path before the same tool calls fire again.

```text
1. Record        - model calls, tools, state snapshots, checkpoints
2. Inspect       - walk the exact event timeline and state at failure time
3. Replay safely - resume from a checkpoint with side-effecting tools mocked or gated
```

## Why AFR exists

AI agent failures are hard to debug because the decisive state is often gone by the time the failure is noticed. Reproducing the issue can require rerunning model calls, repeating tool calls, and risking duplicated side effects such as emails, payments, database writes, or ticket updates.

AFR keeps the evidence:

- append-only event timelines
- deterministic state reconstruction
- checkpoint inspection
- replay tickets
- side-effect-aware replay policies
- CLI and web UI inspection paths
- SQLite-first local storage
- best-effort redaction at ingest

## What makes AFR different

Most agent observability tools help you see what happened. AFR is aimed at the next step: safely returning to the moment that broke.

The core wedge is **checkpoint replay with side-effect-aware policy enforcement**. AFR reconstructs the run state and prepares a replay plan; your resume handler decides how tool calls are handled during replay, including mock, skip, block, and allow decisions.

That makes AFR useful for local debugging today and points toward a larger goal: auditable, privacy-preserving trust infrastructure for autonomous agent systems.

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

## License

Agent Flight Recorder is released under the [MIT License](LICENSE).

Copyright (c) 2026 Terminus Protocol.
