# Integration adapters

AFR records anything that can reach its HTTP API, but adapters make adoption
one line instead of a wiring project.

| Your stack | Path |
| --- | --- |
| Plain Python | SDK decorators + `with afr.start_run(...)` — [sdk.md](sdk.md) |
| LangChain / LangGraph | `AFRCallbackHandler` (below) |
| Anything else | POST JSON to the API ([api.md](api.md)) or duck-type the callback handler |

## LangChain / LangGraph

Install the optional extra (keeps the base SDK dependency-free):

```bash
pip install 'afr-sdk[langchain]'      # adds langchain-core
```

Attach the handler wherever LangChain accepts callbacks:

```python
import afr
from afr.integrations.langchain import AFRCallbackHandler

handler = AFRCallbackHandler(default_tool_policy="side_effecting")

with afr.start_run("langchain-demo"):
    result = chain.invoke(
        {"input": "Plan a refund workflow"},
        config={"callbacks": [handler]},
    )
    afr.checkpoint("after-chain")
```

What gets recorded:

| LangChain callback | AFR event |
| --- | --- |
| `on_llm_start` / `on_chat_model_start` → `on_llm_end` | `model_call` (with prompts, output, token usage, duration) |
| `on_llm_error` | `model_call` (status=error) + `error` |
| `on_tool_start` → `on_tool_end` | `tool_call` (with replay policy stamped) |
| `on_tool_error` | `tool_call` (status=error) + `error` |
| `on_chain_start` / `on_chain_end` | `log` events (+ optional checkpoint) |
| `on_chain_error` | `error` |

### Parameters

```python
AFRCallbackHandler(
    run_name="my-agent",          # auto-start/end a run when used outside afr.start_run
    capture_prompts=True,         # set False to keep prompts/inputs out of the recorder
    capture_outputs=True,         # set False to keep completions/results out
    default_tool_policy="side_effecting",   # replay policy for unlabelled tools
    tool_policies={"charge": "requires_approval"},  # per-tool overrides
    checkpoint_on_chain_end=False,  # checkpoint when the outermost chain finishes
)
```

- **Inside `with afr.start_run(...)`** (recommended): events join that run;
  `run_name` is ignored. You control checkpoints exactly.
- **Without an active run**: pass `run_name` and the handler starts a run on
  the first callback and ends it when the outermost chain finishes
  (`completed`, or `failed` after `on_chain_error`).

### Version defensiveness

Callback signatures drift across LangChain versions, so the adapter inspects
positional payloads with getattr/dict fallbacks and ignores unknown keyword
arguments. If your LangChain version passes something the adapter doesn't
recognize, you lose that detail — never the event. Importing the module never
requires LangChain; constructing the handler does, unless you pass
`require_langchain=False` (used by tests and LangChain-*like* frameworks that
duck-type the same callback methods).

### Try it offline

```bash
make demo-langchain    # examples/langchain_like_agent — fake chain, no API keys
```

The demo emits the exact callback sequence LangChain would, records a failed
refund run with a `before-refund` checkpoint, and prints the mock_tools
replay plan showing the refund tool mocked.

## Custom frameworks

Two options, in order of effort:

1. **Duck-type the callback handler** — if your framework has lifecycle hooks,
   instantiate `AFRCallbackHandler(require_langchain=False)` and call its
   `on_*` methods with LangChain-shaped payloads (see
   `examples/langchain_like_agent/agent.py` for the exact shapes).
2. **Use the HTTP API directly** — create a run, POST events, checkpoint,
   replay. The whole surface is ~10 endpoints ([api.md](api.md)) and the
   seed script (`scripts/seed_demo_run.py`) plus smoke test
   (`scripts/smoke.py`) are stdlib-only working examples.

Planned adapters (OpenAI Agents SDK, CrewAI, OpenAI-compatible proxy mode):
see [roadmap.md](roadmap.md).
