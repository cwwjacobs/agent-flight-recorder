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

## Modes (MVP)

| Mode | Behaviour |
| --- | --- |
| `dry_run` (default) | fetch ticket, print/return state, execute nothing |
| anything else | passed through to your handler untouched |

The MVP trusts your handler to interpret the mode. The Premium tier replaces
this with an enforced safety-policy engine (`dry_run` / `mock_tools` /
`allow_safe_tools` / `allow_side_effects` with per-tool policies, mocked
side-effecting tools by default, and approval gates).
