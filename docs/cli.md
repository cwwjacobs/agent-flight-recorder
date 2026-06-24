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
| `afr regression-case <run_id> --from <ckpt> -o <dir>` | pytest regression-case template from a checkpoint |
| `afr fork <run_id> --from <ckpt> [--name N]` | fork a new run from a checkpoint (premium) |
| `afr tag <run_id> TAG... [--remove]` | add/remove run tags (premium) |
| `afr note <run_id> TEXT [--append]` | set run notes (premium) |
| `afr license` | show plan + feature flags |

Replay modes: `dry_run` (default) · `mock_tools` · `allow_safe_tools`† ·
`allow_side_effects`† († premium; `--approved` unblocks `requires_approval`
tools in `allow_side_effects` mode).

## Examples

```bash
afr runs list --status failed
afr events 648c2cd9 --type tool_call
afr replay 648c2cd9 --from dfd2082b                 # dry run, prints state
afr replay 648c2cd9 --from dfd2082b --mode mock_tools \
    --handler examples.toy_agent.replay_handler:resume
afr export 648c2cd9 -o incident-42.json
afr regression-case 648c2cd9 --from dfd2082b -o cases/incident-42
```

Export format: `{"format": "afr.export.v1", "run": ..., "events": [...],
"checkpoints": [...]}` — stable, diff-able, safe to attach to a ticket.

Regression-case generation writes `case.json`, a skipped pytest template, and a
README into the output directory. It captures exported run metadata, event
counts, reconstructed checkpoint state, and an optional dry-run replay-ticket
reference when `AFR_REPLAY_ENABLED=true`. The generated pytest file is a
template: you still supply the agent or resume function and the domain-specific
assertions.
