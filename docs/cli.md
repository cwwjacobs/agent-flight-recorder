# CLI reference (`afr`)

Global flags: `-A/--api-url URL` (else `$AFR_API_URL`, else `.afr/config.json`,
else `http://127.0.0.1:8700`), `--json` for raw JSON output.

Run and checkpoint ids accept **unique prefixes** — the first 8 characters are
usually enough.

| Command | What it does |
| --- | --- |
| `afr init` | write `.afr/config.json` (api_url) in the cwd |
| `afr runs list [--status S] [--limit N]` | run manifest |
| `afr runs show <run_id>` | run details + checkpoint table |
| `afr events <run_id> [--type T] [--limit N]` | timeline (✗ marks failures) |
| `afr replay <run_id> --from <ckpt> [--mode M] [--handler module:fn]` | request replay; invoke resume handler unless `dry_run` |
| `afr export <run_id> [-o FILE]` | portable JSON bundle (run + events + checkpoints) |

## Examples

```bash
afr runs list --status failed
afr events 648c2cd9 --type tool_call
afr replay 648c2cd9 --from dfd2082b                 # dry run, prints state
afr replay 648c2cd9 --from dfd2082b --mode mock_tools \
    --handler examples.toy_agent.replay_handler:resume
afr export 648c2cd9 -o incident-42.json
```

Export format: `{"format": "afr.export.v1", "run": ..., "events": [...],
"checkpoints": [...]}` — stable, diff-able, safe to attach to a ticket.
