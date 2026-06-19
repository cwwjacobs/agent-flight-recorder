# Premium features

Enable with `AFR_PREMIUM_ENABLED=true` (license boundary **placeholder** —
there is no real billing; see `backend/app/license.py`).

The free/premium boundary is enforced in one module
(`backend/app/license.py`) so a real entitlement check can replace the env
flag without touching anything else.

| Feature | Free | Premium |
| --- | :-: | :-: |
| Recorder (SDK/API/CLI), timeline UI, checkpoints, state-at | ✓ | ✓ |
| Replay: `dry_run`, `mock_tools` | ✓ | ✓ |
| Default secret-key redaction | ✓ | ✓ |
| Replay: `allow_safe_tools`, `allow_side_effects` + per-tool policy plans | — | ✓ |
| Forked replay (branch a run from a checkpoint) | — | ✓ |
| JSON state diff viewer | — | ✓ |
| Run tags & notes (+ tag filters) | — | ✓ |
| Custom redactor hooks | — | ✓ |
| MCP server stub | — | ✓ |

## Replay safety policies

Tag tools with a policy when you record:

```python
@afr.record_tool_call(policy="safe")              # read-only
def search(q): ...

@afr.record_tool_call(policy="requires_approval") # dangerous
def send_email(to, body): ...
```

Policies: `safe` · `side_effecting` (default for unlabelled tools) ·
`mock_by_default` · `requires_approval`.

Replay modes and what each tool's plan action becomes:

| mode | safe | side_effecting | mock_by_default | requires_approval |
| --- | --- | --- | --- | --- |
| `dry_run` (default) | skip | skip | skip | skip |
| `mock_tools` | mock | mock | mock | mock |
| `allow_safe_tools` | **allow** | mock | mock | mock |
| `allow_side_effects` | **allow** | **allow** | mock | **allow** if `approved` else **block** |

The replay ticket (shown as the **Replay Plan** in the UI) carries
`tool_plan` (per-tool action) and `mock_results` (the last recorded
successful result for every mocked tool — record/replay mocking for free).
The server computes the plan; your resume handler enforces it, and
`ctx.call_tool` makes that automatic:

```python
@afr.register_resume_handler
def resume(ctx: afr.ReplayContext):
    # allow -> executes · mock -> recorded result · skip -> default · block -> raises
    hits = ctx.call_tool("search", search, q, default=[])
```

## Forked replay

```bash
afr fork <run_id> --from <checkpoint_id> --name "what-if"
```

or `POST /runs/{run_id}/fork {"checkpoint_id": ...}`. The fork is a new run
seeded with the checkpoint's state; lineage is recorded both ways and shown
in the UI (parent banner ⑂, fork list, fork buttons in the checkpoint
browser).

## Redaction

Default key redaction is **always on**, free or premium, because shipping
secrets to disk is not a feature tier. Substring matches (case-insensitive)
cover `api_key`, `authorization`, `password`, `secret`, `access_token`,
`refresh_token`, `session_token`, `private_key`, `credential`, `cookie`, …;
exact matches cover bare `token`, `bearer`, `auth`, `jwt`. Deliberately *not*
matched: usage telemetry like `prompt_tokens`, `completion_tokens`,
`total_tokens`, `token_count` — your token metrics survive. Disable with
`AFR_REDACTION_ENABLED=false`; extend with `AFR_REDACT_KEYS=ssn,internal_id`.

Premium adds custom redactor hooks:

```python
# backend embedders
from app.redaction import register_redactor

# SDK side (never leaves your process)
@afr.redaction.register_redactor
def scrub(payload: dict) -> dict: ...
afr.redaction.enable_default_redaction()   # optional client-side defaults
```

Redacted values are stored as the literal `"[REDACTED]"`; the UI renders them
as an explicit ⛨ chip.

## Tags & notes

```bash
afr tag <run_id> regression prod      # add
afr tag <run_id> prod --remove        # remove
afr note <run_id> "Found the bug here" [--append]
afr runs list --tag regression
```

API: `PATCH /runs/{run_id}` with `{name?, tags?, notes?}`.

## MCP stub

See [mcp.md](mcp.md).
