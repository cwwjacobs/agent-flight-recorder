# Agent Flight Recorder

[![CI](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml/badge.svg)](https://github.com/cwwjacobs/agent-flight-recorder/actions/workflows/ci.yml)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

**AI agent observability, replay debugging, and checkpoint inspection for LLM apps.**

Your agent did something weird at 2 AM. The logs are a soup of print statements, the
state that caused it is gone, and reproducing the failure means re-running 40 model
calls and hoping. **Agent Flight Recorder (AFR)** is the black box you bolt onto any
Python agent: it records every model call, tool call, state snapshot, and checkpoint
into a structured timeline you can inspect, query, and **replay from any checkpoint** —
all self-hosted, all in SQLite, no cloud account required.

```text
1. Record   — model calls, tools, state snapshots, checkpoints
2. Inspect  — see the exact timeline and state at the moment of failure
3. Replay safely — resume from a checkpoint with side-effecting tools mocked or gated
```

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

## Try it in 90 seconds

```bash
docker compose up --build     # backend + UI on http://localhost:8700
make demo-docker              # seed the demo incident: checkout-agent-payment-timeout
open http://localhost:8700    # (or just click the "Create a demo incident" button in the UI)
```

The demo is a checkout agent that plans, reserves inventory, **checkpoints
before charging the customer**, then the payment call times out. Open the
failed run, walk the timeline to the error, select the `safe-before-side-effect`
checkpoint, and press **Prepare replay plan** in `mock_tools` mode: the plan
shows `charge_customer` is *mocked* — you can debug from before the dangerous
step without charging anyone twice.

## Quickstart without Docker

```bash
make install            # venv + backend + sdk + cli (editable)
make serve              # backend on http://127.0.0.1:8700

# in another shell:
make build-ui           # build the web UI once; the backend serves it at :8700
make demo               # record a toy agent run through the SDK
make demo-langchain     # record a run through the LangChain adapter (no API keys)
afr doctor              # not sure what's wrong? this tells you
```

Open **http://127.0.0.1:8700** → the runs dashboard. Click a run, walk the
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

## Integrations

| Your stack | How to attach AFR |
| --- | --- |
| **Plain Python** | decorators + `with afr.start_run(...)` (above) |
| **LangChain / LangGraph** | one callback handler — see below |
| **Custom framework** | anything that can POST JSON: [docs/api.md](docs/api.md), or duck-type the callback handler |

```python
import afr
from afr.integrations.langchain import AFRCallbackHandler   # pip install 'afr-sdk[langchain]'

handler = AFRCallbackHandler(default_tool_policy="side_effecting")

with afr.start_run("langchain-demo"):
    result = chain.invoke(
        {"input": "Plan a refund workflow"},
        config={"callbacks": [handler]},
    )
    afr.checkpoint("after-chain")
```

Details, parameters, and the adapter roadmap (OpenAI Agents SDK, CrewAI,
proxy mode): [docs/integrations.md](docs/integrations.md) ·
[docs/roadmap.md](docs/roadmap.md).

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
anything. To be precise about the safety story: **the server prepares a
per-tool safety plan and reconstructs state — it never executes your code.**
Your resume handler enforces the plan, and the SDK makes that one line:

```python
hotel = ctx.call_tool("search_hotels", search_hotels, "Tokyo", nights=3, default={})
# allow -> executes · mock -> recorded result · skip -> default · block -> raises
```

The full contract is documented in [docs/replay.md](docs/replay.md).

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
sdk/       afr — Python SDK (client, context, hooks, wrappers, integrations/)
cli/       afr_cli — the afr command (incl. afr doctor)
ui/        Vite + React + TS web UI (3 themes)
examples/  toy_agent + langchain_like_agent — runnable offline demo agents
scripts/   seed_demo_run.py, smoke.py — stdlib-only helpers for a running server
docs/      quickstart, SDK, CLI, API, replay contract, data model, integrations
```

---

# ◆ AFR Premium

**Stop reading diffs in your head. Stop re-running side effects to debug.**
Premium turns the recorder into a debugger:

> ### ⑂ Forked replay
> Branch a brand-new run off any checkpoint. Try the fix, keep the evidence.
> Parent ↔ fork lineage is recorded and browsable in the UI.
>
> ### 🛡 Replay safety policies
> Tag tools `safe` / `side_effecting` / `mock_by_default` /
> `requires_approval`. Replay in `dry_run`, `mock_tools`,
> `allow_safe_tools`, or `allow_side_effects` — **side-effecting tools are
> mocked unless you explicitly allow them**, with recorded results served as
> mocks and approval gates on the dangerous ones.
>
> ### ⇄ JSON state diff
> Pick any two checkpoints or snapshots, get a structural diff:
> added / removed / changed, path by path.
>
> ### ⛨ Redaction
> `api_key`, `authorization`, `password`, `secret`, `access_token`, … scrubbed
> at ingest by default (yes, even in free mode — secrets aren't a feature
> tier), while usage telemetry like `prompt_tokens` / `total_tokens` survives.
> Premium adds custom redactor hooks (backend + SDK) and the UI marks every
> redacted field explicitly.
>
> ### 🏷 Tags, notes, filters
> Tag runs, annotate incidents, filter the timeline by type or failures-only.
>
> ### ⌬ MCP server stub
> An MCP-shaped tool surface (`afr_list_runs`, `afr_replay`, `afr_fork_run`, …)
> so LLM clients can inspect and replay runs. Stub today, cleanly structured
> to become real.

### Enable it

```bash
AFR_PREMIUM_ENABLED=true make serve        # license placeholder — no billing yet
```

| Capability | Free | Premium |
| --- | :-: | :-: |
| Recorder, timeline, checkpoints, state-at, CLI | ✓ | ✓ |
| Replay (`dry_run`, `mock_tools`) | ✓ | ✓ |
| Default secret redaction | ✓ | ✓ |
| Policy modes (`allow_safe_tools`, `allow_side_effects`) | — | ✓ |
| Forked replay + lineage | — | ✓ |
| State diff viewer | — | ✓ |
| Tags, notes, custom redactors, MCP stub | — | ✓ |

## Docker & deployment

```bash
docker compose up --build      # backend + UI + persistent SQLite volume
```

The compose file binds to **127.0.0.1 only** by default — recorded prompts and
state are sensitive, and the server ships with no auth out of the box. To
expose it beyond localhost, set `AFR_API_TOKEN` (bearer-token auth on all
run/data endpoints) and change the port binding deliberately. Details:
[docs/docker.md](docs/docker.md) · [SECURITY.md](SECURITY.md).

## Docs

| Doc | What's in it |
| --- | --- |
| [docs/quickstart.md](docs/quickstart.md) | install → record → inspect → replay |
| [docs/sdk.md](docs/sdk.md) | full SDK reference |
| [docs/cli.md](docs/cli.md) | CLI reference |
| [docs/api.md](docs/api.md) | HTTP API reference |
| [docs/replay.md](docs/replay.md) | the replay contract |
| [docs/data-model.md](docs/data-model.md) | tables, event types, state folding |
| [docs/premium.md](docs/premium.md) | premium features in depth |
| [docs/docker.md](docs/docker.md) | container deploy, hardening env vars |
| [docs/integrations.md](docs/integrations.md) | LangChain adapter + custom frameworks |
| [docs/roadmap.md](docs/roadmap.md) | what's next (adapters, proxy mode, team mode) |
| [docs/mcp.md](docs/mcp.md) | MCP stub |

## Tests

```bash
make test    # storage, state reconstruction, API/SDK smoke, redaction,
             # replay policies + ctx.call_tool, forking, license gating,
             # auth tokens, demo seed, LangChain adapter, afr doctor, MCP
make smoke   # end-to-end check against a *running* backend
```

## Repo history

The MVP is preserved intact: commit `mvp-agent-flight-recorder` and the
frozen snapshot in `dist/mvp-agent-flight-recorder/`. Premium is built on
top without rewriting it.
