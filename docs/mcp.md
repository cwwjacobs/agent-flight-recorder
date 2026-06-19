# MCP-shaped HTTP prototype (opt-in / experimental)

AFR ships an MCP-shaped tool layer so the AFR engine's surface is exposed in
MCP terms. **It is an explicit prototype, not a conformant MCP server.** The
tool registry, JSON-Schema definitions, and call dispatch are real and tested
and reachable over plain HTTP — but there is **no stdio / SSE / JSON-RPC MCP
transport**, so MCP clients (Claude Code, etc.) cannot connect to it yet.
`backend/app/mcp/server.py` documents exactly where a real transport goes.

This is an opt-in (experimental) feature — enable it with
`AFR_EXPERIMENTAL_FEATURES_ENABLED=true`.

## Tools

| Tool | Purpose |
| --- | --- |
| `afr_list_runs` | list runs (status/tag filters) |
| `afr_get_run` | one run incl. tags, notes, fork lineage |
| `afr_get_events` | a run's timeline |
| `afr_get_state_at_checkpoint` | reconstructed state at a checkpoint |
| `afr_replay` | request a replay ticket (safe-by-default policy engine) |
| `afr_fork_run` | fork a run from a checkpoint |
| `afr_tag_run` | replace a run's tags |

## HTTP prototype

With `AFR_EXPERIMENTAL_FEATURES_ENABLED=true` (and `Authorization: Bearer
<token>` if the server sets `AFR_API_TOKEN` — `/mcp/*` is a protected route):

```bash
curl http://127.0.0.1:8700/mcp/tools

curl -X POST http://127.0.0.1:8700/mcp/call \
  -H 'Content-Type: application/json' \
  -d '{"tool": "afr_list_runs", "arguments": {"limit": 5}}'
```

Responses: `{"ok": true, "tool": ..., "result": ...}`; errors map to 404
(unknown tool/run), 422 (bad arguments), 403 (feature disabled).

## Manifest dump

```bash
AFR_EXPERIMENTAL_FEATURES_ENABLED=true python -m app.mcp.server   # from backend/
```

## Making it real

Wire `app/mcp/tools.py` (name, description, JSON-Schema, handler — already
MCP-shaped) to the official `mcp` Python SDK inside `server.py`. No other
module needs to change.
