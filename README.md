# Agent Flight Recorder

[![CI](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml/badge.svg)](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Local-first recorder for observable tool-using agent runs.**

Agent Flight Recorder (AFR) records the operational evidence of an agent run:

- model calls and model responses
- tool calls and tool results
- state snapshots
- checkpoints
- errors
- replay requests and replay-plan events

From those recorded events, AFR can inspect a run in the browser, export a portable run bundle, and generate regression-case material.

AFR does not expose a model's unrecorded internals, private reasoning traces, neural state, or true internal intent. It preserves execution evidence that was actually recorded through the SDK, API, CLI, or adapter path in use.

```text
1. Record           - capture observable execution evidence
2. Inspect          - review the run timeline, state, checkpoints, and failures
3. Export           - download a portable JSON run bundle
4. Replay plan      - reconstruct recorded state and choose safe tool policies
5. Regression case  - turn a checkpoint into a pytest fixture for the repair
```

## Download and run

The recommended path needs **Docker Desktop only**. Python and Node run inside the image.

1. Download the repository ZIP or the `agent-flight-recorder-portable` CI artifact and extract it.
2. Start AFR:

   **Windows:** double-click `start.cmd`

   **macOS or Linux:**

   ```bash
   sh start.sh
   ```

3. The launcher builds the complete image, waits for the health check, and opens:

   ```text
   http://127.0.0.1:8700
   ```

The image includes the web UI, FastAPI backend, Python SDK, and `afr` CLI. Data persists in the local Docker volume `afr-data`.

The direct command is also one line:

```bash
docker compose up --build
```

Useful container commands:

```bash
docker compose exec afr afr doctor
docker compose exec afr afr runs list
docker compose exec afr afr demo
docker compose logs -f afr
docker compose down                 # keeps recorded data
docker compose down -v              # deletes recorded data too
```

The empty-state screen can create a complete payment-timeout demo incident with one click.

## Local contributor setup

Use this path when you already have Python 3.10+ and Node installed:

```bash
make install
make build-ui
make run                    # UI and API on http://127.0.0.1:8700
```

Or run the layers separately:

```bash
make serve                  # serves ui/dist when it exists
cd ui && npm run dev        # Vite dev server on http://127.0.0.1:5173
```

`make package` creates `dist/agent-flight-recorder-portable.zip` with prebuilt UI assets.

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
- browser and CLI inspection paths
- SQLite-first local storage
- best-effort redaction at ingest

## What AFR does

AFR is intended for local development, debugging, evaluation, and incident reproduction. It helps answer practical questions:

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

## Browser workflow

The bundled UI provides:

- backend health and version status
- searchable and filterable run history
- responsive run cards on small screens
- keyboard-accessible run navigation
- live refresh that can be paused
- event timeline and payload inspection
- checkpoint and reconstructed-state inspection
- replay-plan preparation with explicit safety modes
- state comparison where enabled
- one-click local JSON bundle download
- light, dark, and Cyber Orchid themes

## CLI workflow

```bash
afr runs list --status failed
afr runs show 648c2cd9
afr events 648c2cd9 --errors-only
afr export 648c2cd9 -o incident-42.json
afr-regression-case 648c2cd9 --from dfd2082b -o cases/payment-timeout
```

With Docker, prefix those commands with `docker compose exec afr`.

The generated regression case contains `case.json`, a pytest template, and a README. It is safe by default: it gives you a fixture for asserting repaired behavior, not a mechanism for surprise side effects.

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

Replay is deliberately disabled by default. Enable it only when you want to request replay tickets or invoke resume handlers:

```bash
export AFR_REPLAY_ENABLED=true
AFR_REPLAY_ENABLED=true docker compose up --build
```

```python
import afr

@afr.register_resume_handler
def resume(ctx: afr.ReplayContext):
    agent = MyAgent.from_state(ctx.state)
    return agent.continue_run()

afr.replay(run_id, checkpoint_id, mode="mock_tools")
```

The server reconstructs recorded state and prepares a replay ticket. It does not execute user code. The resume handler enforces the plan when it uses the SDK helpers, including mock, skip, block, and allow decisions for tool calls.

## Integrations

| Stack | AFR attachment path |
| --- | --- |
| Plain Python | decorators + `with afr.start_run(...)` |
| LangChain / LangGraph | optional callback handler |
| Custom framework | HTTP API or SDK calls |
| Codex | `Codex-AFR/` wrapper and harness |
| MCP clients | local HTTP MCP surface |

See:

- [Quickstart](docs/quickstart.md)
- [Dependency map and weaknesses](docs/dependency-map.md)
- [SDK](docs/sdk.md)
- [CLI](docs/cli.md)
- [API](docs/api.md)
- [Replay](docs/replay.md)
- [Data model](docs/data-model.md)
- [Integrations](docs/integrations.md)
- [Evals](docs/evals.md)
- [Roadmap](docs/roadmap.md)
- [MCP](docs/mcp.md)

## Security model

AFR is localhost-first. Recorded prompts, tool payloads, and state snapshots can contain sensitive information.

- The backend binds to `127.0.0.1` by default for local runs.
- Docker publishes the service to `127.0.0.1:8700` on the host by default.
- CORS is restricted to local AFR origins by default.
- Set `AFR_API_TOKEN=<token>` before exposing AFR outside loopback.
- Redaction runs at ingest and is best-effort, not a guarantee.
- Treat the SQLite database and exported run bundles as sensitive at rest.
- Replay remains disabled unless `AFR_REPLAY_ENABLED=true` is explicitly set.

## Repository layout

```text
backend/    FastAPI app: API, replay engine, storage, schemas
sdk/        Python SDK: client, context, hooks, wrappers, integrations
cli/        afr CLI and regression-case generator
ui/         React/Vite inspection interface
Codex-AFR/  Codex wrapper, hook bridge, package helpers, and smoke test
examples/   runnable offline demo agents
scripts/    demo and smoke helpers
docs/       product and integration documentation
evals/      small public eval seed records for AFR behavior
```

## Tests

```bash
make test
make build-ui
make smoke                    # against a running backend
docker compose up --build     # integrated image path
```

CI verifies the Python suite, UI typecheck/build, integrated Docker image, bundled CLI, and portable ZIP assembly.

## Project status

AFR is a public OSS baseline maintained by Corey Jacobs / cwwjacobs. The project is Apache-2.0 licensed with Terminus Protocol copyright and notice metadata preserved in the repository.

Current focus areas:

- hardening replay policy behavior
- expanding adapter coverage beyond the current Python and LangChain / LangGraph paths
- improving diff and checkpoint inspection flows
- preserving local-first privacy while making agent failures easier to reproduce safely
- turning repaired failure shapes into regression cases and eval seeds
- adding event pagination or windowed rendering for very large runs
- moving from manual direct pins to a hash-verified Python lock workflow

See:

- [LICENSE](LICENSE)
- [NOTICE](NOTICE)
- [OPEN_SOURCE_FREEZE.md](OPEN_SOURCE_FREEZE.md)

## License

Agent Flight Recorder is released under the [Apache License 2.0](LICENSE).

Copyright (c) 2026 Terminus Protocol.
