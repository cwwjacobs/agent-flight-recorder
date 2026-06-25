# Agent Flight Recorder

[![CI](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml/badge.svg)](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Local-first recorder for observable tool-using agent runs.**

Agent Flight Recorder (AFR) records the operational evidence of an agent run:

- model calls
- tool calls
- tool results
- state snapshots
- checkpoints
- errors
- replay requests

From those recorded events, AFR can export portable run bundles and generate regression-case material.

When an agent fails, AFR preserves what the agent received, what the model returned, what tools were requested, what those tools returned, what state was recorded, where checkpoints were created, and what errors ended the run.

AFR does not expose a model's unrecorded internals, private reasoning traces, neural state, or true internal intent. It preserves execution evidence that was actually recorded through the SDK, API, CLI, or adapter path in use.

```text
1. Record           - capture model calls, tool calls, tool results, state snapshots, checkpoints, errors, and replay requests
2. Inspect          - review the recorded event timeline and recorded state around a failure
3. Export           - preserve a portable JSON run bundle
4. Regression case  - turn a checkpoint into a pytest fixture for the repair
5. Eval seed        - promote recurring failure shapes into eval records
```

## Why AFR exists

Tool-using agents can fail after prompts, tool calls, state updates, or external side effects have already happened. By the time the failure is noticed, the run context may be scattered across logs or gone.

AFR keeps a local record of the run evidence:

- append-only recorded event timelines
- model calls and model responses
- tool calls and tool results
- recorded state snapshots and checkpoint metadata
- checkpoint inspection
- replay tickets and replay plans
- side-effect-aware replay helpers
- CLI-first inspection and export paths
- SQLite-first local storage
- best-effort redaction at ingest

## What AFR does

AFR is intended for local development, debugging, evaluation, and audit workflows. It helps answer practical questions:

- What did the agent receive?
- What did the model return?
- What tools were requested or executed?
- What did those tools return?
- What state was recorded before the failure?
- Which checkpoint can be used to prepare a replay request?
- Which side-effecting tools should be mocked, skipped, blocked, or explicitly allowed?
- Which failure should become a regression case or eval seed?

The replay boundary is explicit. The backend reconstructs recorded state and prepares a replay ticket. It does not execute user code. A user-provided resume handler owns replay execution and should use the SDK helpers to honor mock, skip, block, and allow decisions.

## What AFR does not claim

AFR is not a model interpretability system. It does not recover true model intent, private reasoning traces, neural activations, or training traces.

AFR is not an enterprise security product or sandbox by itself. Recorded prompts, tool payloads, and state snapshots can contain sensitive data. Redaction is best-effort, not a guarantee.

AFR is not a guarantee that every state change was captured. State reconstruction is limited to events and snapshots actually recorded by the SDK, CLI, API, or adapter path in use.

## Quickstart

Docker starts the backend API on `http://127.0.0.1:8700` and stores data in a local Docker volume:

```bash
docker compose up --build     # backend API on http://127.0.0.1:8700
make demo-docker              # seed the checkout-agent-payment-timeout demo incident
afr runs list
```

Without Docker:

```bash
make install
make serve                    # API on http://127.0.0.1:8700
make demo
afr doctor
afr runs list
```

Replay is deliberately disabled by default. Enable it only when you want to request replay tickets or invoke resume handlers:

```bash
export AFR_REPLAY_ENABLED=true
# Docker: pass the same variable into compose
AFR_REPLAY_ENABLED=true docker compose up --build
```

## CLI-first spine

```bash
afr runs list --status failed
afr runs show 648c2cd9
afr events 648c2cd9 --errors-only
afr export 648c2cd9 -o incident-42.json
afr-regression-case 648c2cd9 --from dfd2082b -o cases/payment-timeout
```

The generated regression case contains `case.json`, a pytest template, and a README. It is safe by default: it gives you a fixture for asserting the repaired behavior, not a mechanism for surprise side effects.

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

# Requires AFR_REPLAY_ENABLED=true in the replaying process and backend.
afr.replay(run_id, checkpoint_id, mode="mock_tools")
```

The server reconstructs recorded state and prepares a replay ticket. It does not execute user code. The resume handler enforces the plan when it uses the SDK helpers, including mock, skip, block, and allow decisions for tool calls.

## Integrations

| Stack | AFR attachment path |
| --- | --- |
| Plain Python | decorators + `with afr.start_run(...)` |
| LangChain / LangGraph | callback handler |
| Custom framework | HTTP API or SDK calls |
| Codex | `Codex-AFR/` wrapper and harness |

See:

- [docs/quickstart.md](docs/quickstart.md)
- [docs/sdk.md](docs/sdk.md)
- [docs/cli.md](docs/cli.md)
- [docs/api.md](docs/api.md)
- [docs/replay.md](docs/replay.md)
- [docs/data-model.md](docs/data-model.md)
- [docs/integrations.md](docs/integrations.md)
- [docs/evals.md](docs/evals.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/mcp.md](docs/mcp.md)

## Security model

AFR is localhost-first. Recorded prompts, tool payloads, and state snapshots can contain sensitive information.

- The backend binds to `127.0.0.1` by default for local runs.
- Docker publishes the service to `127.0.0.1:8700` on the host by default.
- CORS is restricted to local AFR origins by default.
- Set `AFR_API_TOKEN=<token>` before exposing AFR outside loopback.
- Redaction runs at ingest and is best-effort, not a guarantee.
- Treat the SQLite database as sensitive at rest.

## Repository layout

```text
backend/   FastAPI app: API, replay engine, storage, schemas
sdk/       Python SDK: client, context, hooks, wrappers, integrations
cli/       afr CLI
Codex-AFR/ Codex wrapper, hook bridge, package helpers, and smoke test
examples/  runnable offline demo agents
scripts/   demo and smoke helpers
docs/      quickstart, SDK, CLI, API, replay, data model, integrations, evals
evals/     small public eval seed records for AFR behavior
```

## Tests

```bash
make test
make smoke
```

## Project status

AFR is a public OSS baseline maintained by Corey Jacobs / cwwjacobs. The project is Apache-2.0 licensed with Terminus Protocol copyright and notice metadata preserved in the repository.

Current focus areas:

- hardening replay policy behavior
- expanding adapter coverage beyond the current Python and LangChain / LangGraph paths
- improving diff and checkpoint inspection flows
- preserving local-first privacy while making agent failures easier to reproduce safely
- turning repaired failure shapes into regression cases and eval seeds

See:

- [LICENSE](LICENSE)
- [NOTICE](NOTICE)
- [OPEN_SOURCE_FREEZE.md](OPEN_SOURCE_FREEZE.md)

## License

Agent Flight Recorder is released under the [Apache License 2.0](LICENSE).

Copyright (c) 2026 Terminus Protocol.
