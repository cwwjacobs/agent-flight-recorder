# Agent Flight Recorder

**AI agent observability, replay debugging, and checkpoint inspection for LLM apps.**

Your agent did something weird at 2 AM. The logs are a soup of print statements, the
state that caused it is gone, and reproducing the failure means re-running 40 model
calls and hoping. **Agent Flight Recorder (AFR)** is the black box you bolt onto any
Python agent: it records every model call, tool call, state snapshot, and checkpoint
into a structured timeline you can inspect, query, and **replay from any checkpoint** —
all self-hosted, all in SQLite, no cloud account required.

```
┌──────────────┐   afr SDK    ┌───────────────┐   SQLite    ┌─────────────────┐
│  your agent   ├─────────────▶│  AFR backend  ├────────────▶│  append-only     │
│  (any Python) │  HTTP/JSON   │  (FastAPI)    │             │  event timeline  │
└──────────────┘              └──────┬────────┘             └─────────────────┘
                                     │
                      ┌──────────────┼─────────────────┐
                      ▼              ▼                  ▼
                 web UI (React)   afr CLI        replay tickets →
                 timeline/state   inspect/export  your resume handler
```

## What you get

- **Full-fidelity recording** — `model_call`, `tool_call`, `state_snapshot`,
  `checkpoint`, `log`, and `error` events in an append-only SQLite timeline.
- **Checkpoint inspection** — exact agent state *as of any checkpoint*,
  reconstructed deterministically from recorded snapshots.
- **Replay debugging** — a clean replay contract: the backend reconstructs state
  and hands a *replay ticket* to a resume handler you register. Your agent picks
  up where it left off; the server never executes your code.
- **Operator-console web UI** — vertical event timeline, expandable JSON payloads,
  checkpoint highlighting, failure highlighting, state inspector, replay button.
  Three themes: **Light**, **Dark**, and the signature **Cyber Orchid**.
- **A real CLI** — `afr runs list`, `afr events`, `afr replay`, `afr export`.
- **Tiny dependency footprint** — FastAPI + SQLite + httpx. That's the stack.

## Quickstart (60 seconds)

```bash
make install            # venv + backend + sdk + cli (editable)
make serve              # backend on http://127.0.0.1:8700

# in another shell:
make demo               # records a toy agent run (model calls, tools, a failure, checkpoints)
make build-ui           # build the web UI once; the backend serves it at :8700
```

Open **http://127.0.0.1:8700** → the run manifest. Click the run, walk the
timeline, expand payloads, select a checkpoint, view its state, press replay.

Prefer raw commands? See [docs/quickstart.md](docs/quickstart.md).

## Record your agent (SDK)

```python
import afr

@afr.record_tool_call
def search_flights(destination: str, budget_usd: int) -> dict:
    ...

@afr.record_model_call(model="gpt-x", provider="openai")
def ask_llm(prompt: str) -> str:
    ...

with afr.start_run("trip-planner", metadata={"env": "dev"}):
    plan = ask_llm("plan a trip to Tokyo")        # recorded automatically
    flights = search_flights("Tokyo", 900)        # recorded automatically
    afr.log_state({"booked": {"flight": flights}}, mode="merge")
    afr.checkpoint("after-flights")               # ← you can replay from here
```

Everything is also available as explicit calls (`afr.log_model(...)`,
`afr.log_tool(...)`, `afr.log_event(...)`) when you want manual control.
Exceptions inside the `with` block are recorded as `error` events and the run
is marked `failed` — you keep the evidence.

## Replay from a checkpoint

```python
import afr

@afr.register_resume_handler
def resume(ctx: afr.ReplayContext):
    agent = MyAgent.from_state(ctx.state)   # state as of the checkpoint
    return agent.continue_run()

afr.replay(run_id, checkpoint_id, mode="mock_tools")
```

or from the terminal:

```bash
afr replay <run_id> --from <checkpoint_id> --mode mock_tools \
    --handler examples.toy_agent.replay_handler:resume
```

`dry_run` (the default) returns the reconstructed state without invoking
anything. The full contract is documented in [docs/replay.md](docs/replay.md).

## CLI session

```text
$ afr runs list
ID        NAME              STATUS     STARTED              EVENTS  CKPTS
--------  ----------------  ---------  -------------------  ------  -----
648c2cd9  toy-trip-planner  completed  2026-06-11 13:32:41  16      3

$ afr events 648c2cd9
SEQ  !  TIME                 TYPE            NAME            PAYLOAD
7    ✗  2026-06-11 13:32:41  tool_call       search_hotels   {"tool": "search_hotels", ...
...

$ afr export 648c2cd9 -o run.json
exported run 648c2cd9 → run.json
```

## Repo layout

```
backend/   FastAPI app: api/, engine/, storage/, replay/, schemas/
sdk/       afr — Python SDK (client, context, hooks, wrappers)
cli/       afr_cli — the afr command
ui/        Vite + React + TS web UI (3 themes)
examples/  toy_agent — runnable offline demo agent
docs/      quickstart, SDK, CLI, API, replay contract, data model
```

## Docs

| Doc | What's in it |
| --- | --- |
| [docs/quickstart.md](docs/quickstart.md) | install → record → inspect → replay |
| [docs/sdk.md](docs/sdk.md) | full SDK reference |
| [docs/cli.md](docs/cli.md) | CLI reference |
| [docs/api.md](docs/api.md) | HTTP API reference |
| [docs/replay.md](docs/replay.md) | the replay contract |
| [docs/data-model.md](docs/data-model.md) | tables, event types, state folding |

## Tests

```bash
make test    # storage, state reconstruction, API smoke, SDK smoke
```

## Status

This is the MVP: recorder, timeline, checkpoints, state inspection, replay
contract, CLI, UI, docs, tests. Premium tier (state diffs, forked replay,
replay safety policies, redaction, MCP server, Docker) ships on top of it —
see the repo history.
