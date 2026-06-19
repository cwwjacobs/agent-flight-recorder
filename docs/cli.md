# CLI reference (`afr`)

Global flags: `-A/--api-url URL` (else `.afr/config.json`, else
`$AFR_API_URL`, else `http://127.0.0.1:8700`), `--json` for raw JSON output.
Token-protected backend? Export `AFR_API_TOKEN` and every command sends it.

Run and checkpoint ids accept **unique prefixes** — the first 8 characters are
usually enough.

| Command | What it does |
| --- | --- |
| `afr doctor [--read-only]` | check backend reachability, `/health`, `/license`, auth token status, write access, SDK version, API URL in use; prints Docker hints when unreachable |
| `afr init` | write `.afr/config.json` (api_url) in the cwd |
| `afr runs list [--status S] [--tag T] [--limit N]` | run manifest |
| `afr runs show <run_id>` | run details + checkpoints + fork lineage |
| `afr events <run_id> [--type T] [--errors-only] [--limit N]` | timeline (✗ marks failures) |
| `afr replay <run_id> --from <ckpt> [--mode M] [--approved] [--handler module:fn]` | request replay; invoke resume handler unless `dry_run` |
| `afr export <run_id> [-o FILE]` | portable JSON bundle (run + events + checkpoints) |
| `afr fork <run_id> --from <ckpt> [--name N]` | fork a new run from a checkpoint (experimental) |
| `afr tag <run_id> TAG... [--remove]` | add/remove run tags (experimental) |
| `afr note <run_id> TEXT [--append]` | set run notes (experimental) |
| `afr license` | show feature availability + opt-in flags |

Replay modes: `dry_run` (default) · `mock_tools` · `allow_safe_tools`† ·
`allow_side_effects`† († experimental opt-in; `--approved` unblocks
`requires_approval` tools in `allow_side_effects` mode).

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
