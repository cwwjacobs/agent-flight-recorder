# HTTP API reference

Base URL: `http://127.0.0.1:8700` (also mirrored under `/api` for legacy clients).
Interactive docs: `http://127.0.0.1:8700/docs` (FastAPI/OpenAPI).

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/health` | — | service status |
| POST | `/runs` | `{name?, metadata?}` | created run (201) |
| GET | `/license` | auth when configured | plan + feature flags |
| GET | `/runs` | — (`?status=&tag=&limit=&offset=`) | run list incl. `last_error` + `event_type_counts` |
| GET | `/runs/{run_id}` | — | one run incl. fork lineage |
| PATCH | `/runs/{run_id}` | `{name?, tags?, notes?}` | updated run (premium) |
| POST | `/runs/{run_id}/fork` | `{checkpoint_id, name?}` | new run forked from a checkpoint (premium, 201) |
| POST | `/runs/{run_id}/end` | `{status?: completed\|failed}` | updated run |
| POST | `/runs/{run_id}/events` | `{event_type, name?, payload?, created_at?}` | created event (201) |
| GET | `/runs/{run_id}/events` | — (`?event_type=&limit=&offset=`) | events in seq order |
| POST | `/runs/{run_id}/checkpoint` | `{label?, state?}` | created checkpoint (201) |
| GET | `/runs/{run_id}/checkpoints` | — | checkpoints in order |
| GET | `/runs/{run_id}/state-at/{checkpoint_id}` | — (`?reconstruct=true` to re-fold) | `{checkpoint, state, source}` |
| POST | `/runs/{run_id}/replay` | `{checkpoint_id, mode?, approved?}` | replay ticket |
| POST | `/demo/seed` | — | seed the demo incident (201; 403 if `AFR_DEMO_SEED_ENABLED=false`) |
| GET | `/mcp/tools` | — | MCP stub tool registry (premium) |
| POST | `/mcp/call` | `{tool, arguments?}` | invoke an MCP stub tool (premium) |

## Event types

`model_call` · `tool_call` · `state_snapshot` · `checkpoint` · `log` · `error`
(anything else → 422).

## Conventions

- Timestamps are ISO-8601 UTC strings. Clients may supply `created_at` for
  buffered ingest; ordering authority is the server-assigned `seq`.
- Event `payload` is free-form JSON. Recorded tool calls conventionally carry
  `{tool, args, result, status, error?, duration_ms}`; model calls carry
  `{model, provider, input, output, status, duration_ms}`.
- A `state_snapshot` payload is `{state: {...}, mode: "replace"|"merge"}`.
- Appends are accepted after a run ends (late buffers, replay bookkeeping).
- Errors: 404 unknown run/checkpoint, 422 validation, 402 premium feature
  disabled, 401 missing/wrong bearer token (only when `AFR_API_TOKEN` is set).

## Auth (optional)

Unset `AFR_API_TOKEN` (default) = fully open local instance. When set, every
API endpoint at the root and under the `/api` mirror requires:

```
Authorization: Bearer <token>
```

`/health`, the OpenAPI docs, and any served legacy static UI stay open. API clients may send
`Authorization: Bearer <token>` or `X-AFR-Token: <token>`. The SDK and CLI
pick the token up from the `AFR_API_TOKEN` env var automatically.
