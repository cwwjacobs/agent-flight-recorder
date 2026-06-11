# SDK reference (`afr`)

Install: `pip install -e ./sdk` (depends only on `httpx`).

## Starting and ending runs

```python
import afr

run = afr.start_run(
    name="my-agent",                      # optional, auto-named if omitted
    metadata={"env": "prod", "user": 1},  # optional, stored on the run
    api_url="http://127.0.0.1:8700",      # optional ($AFR_API_URL / default)
)
```

`start_run` returns a `RunContext`. Use it as a context manager (recommended):

```python
with afr.start_run("my-agent") as run:
    ...
# exit → run ended as "completed"
# exception → `error` event recorded (with traceback) + run ended as "failed",
#             then the exception propagates
```

or drive it manually: `run.end(status="completed" | "failed")`.

Inside a `with` block the run is the *current run*; module-level helpers and
decorators bind to it automatically.

## Logging

| Call | Event type | Notes |
| --- | --- | --- |
| `afr.log_model(model=, provider=, input=, output=, status=, error=, duration_ms=, **extra)` | `model_call` | all fields optional |
| `afr.log_tool(tool, args=, result=, status=, error=, duration_ms=, **extra)` | `tool_call` | |
| `afr.log_state(state, mode="replace"\|"merge")` | `state_snapshot` | see state semantics below |
| `afr.checkpoint(label=, state=)` | `checkpoint` | returns checkpoint dict with `id` |
| `afr.log(message, level="info", **data)` | `log` | |
| `afr.log_error(message, traceback=, **data)` | `error` | |
| `afr.log_event(event_type, name=, payload=)` | any | manual escape hatch |

All payloads pass through `afr.jsonable()` — objects that aren't JSON-safe are
`repr()`-ed instead of crashing your agent.

### State semantics

- `mode="replace"` (default): this snapshot **is** the new state.
- `mode="merge"`: deep-merged into the current state (dicts merge recursively,
  lists/scalars are replaced).
- `afr.checkpoint(state={...})` pins explicit state; otherwise the checkpoint
  stores the state folded from snapshots so far.

## Decorators

```python
@afr.record_tool_call                      # bare
def search(query: str) -> list: ...

@afr.record_tool_call(name="db.query", capture_result=False)
def query(sql: str) -> list: ...

@afr.record_model_call(model="gpt-x", provider="openai")
def ask(prompt: str) -> str: ...
```

Recorded: args, result, duration, status. Exceptions are recorded
(`status="error"` + an `error` event) and re-raised. **With no active run the
wrapped function executes untouched** — safe to decorate library code.

## Replay

```python
@afr.register_resume_handler
def resume(ctx: afr.ReplayContext):
    # ctx.run_id, ctx.checkpoint_id, ctx.label, ctx.mode, ctx.state
    ...

result = afr.replay(run_id, checkpoint_id, mode="mock_tools")
# {"ticket": {...}, "handler_result": ..., "handler_invoked": True}
```

`mode="dry_run"` (default) fetches the ticket without invoking any handler.
Handlers can also be passed explicitly: `afr.replay(..., handler="my.module:fn")`.

## Low-level client

`afr.AFRClient` exposes the raw API (`create_run`, `append_event`,
`checkpoint`, `state_at`, `replay`, `export_bundle`, ...). Pass
`http_client=` to inject any `httpx.Client`-compatible transport — that's how
the test suite runs the SDK against an in-process app.
