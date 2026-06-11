# MCP server stub (premium)

AFR ships an MCP-shaped tool layer so an LLM client (Claude Code, etc.) can
inspect and replay agent runs. **It is an explicit stub**: the tool registry,
schemas, and dispatch are real and tested; the stdio MCP transport is not
wired yet (`backend/app/mcp/server.py` documents exactly where it goes).

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

## HTTP stub

With `AFR_PREMIUM_ENABLED=true`:

```bash
curl http://127.0.0.1:8700/mcp/tools

curl -X POST http://127.0.0.1:8700/mcp/call \
  -H 'Content-Type: application/json' \
  -d '{"tool": "afr_list_runs", "arguments": {"limit": 5}}'
```

Responses: `{"ok": true, "tool": ..., "result": ...}`; errors map to 404
(unknown tool/run), 422 (bad arguments), 402 (premium disabled).

## Manifest dump

```bash
AFR_PREMIUM_ENABLED=true python -m app.mcp.server   # from backend/
```

## Making it real

Wire `app/mcp/tools.py` (name, description, JSON-Schema, handler — already
MCP-shaped) to the official `mcp` Python SDK inside `server.py`. No other
module needs to change.
