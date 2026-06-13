# The replay contract

Replay is deliberately split in two. The **server** owns history; the
**client** owns execution. The server never runs your code.

```
 you                      AFR backend                    your process
  │  POST /runs/{id}/replay   │                               │
  ├──────────────────────────▶│ validate run + checkpoint     │
  │                           │ reconstruct state @ checkpoint│
  │                           │ append log: replay_requested  │
  │   replay ticket (JSON)    │                               │
  │◀──────────────────────────┤                               │
  │        afr SDK: ticket → ReplayContext → resume handler   │
  ├───────────────────────────────────────────────────────────▶
```

## The ticket

```json
{
  "run_id": "...",
  "checkpoint_id": "...",
  "label": "after-flights",
  "mode": "mock_tools",
  "state": { "...": "state as of the checkpoint" },
  "status": "ready",
  "message": "...",
  "replay_event_id": "..."
}
```

Anything that can read JSON can implement a resume handler — the Python SDK is
just the convenient path.

## Resume handlers (SDK)

```python
@afr.register_resume_handler
def resume(ctx: afr.ReplayContext):
    agent = MyAgent.from_state(ctx.state)
    return agent.continue_run()

afr.replay(run_id, checkpoint_id, mode="mock_tools")
```

- `ctx.state` — deterministic fold of `state_snapshot` events up to the
  checkpoint (see [data-model.md](data-model.md)).
- `mode="dry_run"` — ticket only; the SDK does **not** invoke any handler.
- Any other mode — handler invoked with the ticket's context.
- CLI equivalent: `afr replay <run> --from <ckpt> --mode mock_tools
  --handler my.module:resume`.

- `ctx.call_tool(tool, fn, *args, default=None, **kwargs)` — runs a tool the
  way the plan says to: `allow` executes `fn`, `mock` returns the recorded
  result (or `default`), `skip` returns `default`, `block` raises
  `afr.ToolBlockedError`. Use it and your handler can't execute a
  side-effecting tool by accident.

## Modes

| Mode | Behaviour | Tier |
| --- | --- | --- |
| `dry_run` (default) | plan + state only; the SDK invokes **no** handler | free |
| `mock_tools` | handler runs; every tool is mocked from recorded results | free |
| `allow_safe_tools` | tools recorded `policy="safe"` execute; everything else mocked | premium |
| `allow_side_effects` | side effects execute; `requires_approval` tools blocked unless `approved: true` | premium |

## Who enforces what — read this part

Wording matters here, so to be exact:

- the **server** validates the request, reconstructs state, computes the
  per-tool safety plan (`tool_plan`) and recorded mock results, and logs the
  request on the timeline. It **never executes your code or your tools.**
- the **SDK** provides `ReplayContext` helpers (`call_tool`, `action_for`,
  `should_execute`, `mock_result`) that make honoring the plan one line.
- your **resume handler** is where execution happens. Use the helpers; a
  handler that ignores the plan and calls tools directly gets no protection
  from anyone.

The UI labels the ticket a **Replay Plan** — same JSON document, friendlier
name.
