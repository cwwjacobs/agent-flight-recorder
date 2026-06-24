# CLI reference (`afr`)

Global flags: `-A/--api-url URL` (else `.afr/config.json`, else `$AFR_API_URL`, else `http://127.0.0.1:8700`), `--json` for raw JSON output. Token-protected backend? Export `AFR_API_TOKEN` and every command sends it.

Run and checkpoint ids accept **unique prefixes**. Use `latest` for the newest run or newest checkpoint in a run.

| Command | What it does |
| --- | --- |
| `afr doctor [--read-only]` | check backend reachability, `/health`, `/license`, auth token status, write access, SDK version, API URL in use; prints Docker hints when unreachable |
| `afr init` | write `.afr/config.json` (`api_url`) in the cwd |
| `afr demo [--seed]` | record the toy-agent demo, or seed the polished checkout incident with `--seed` |
| `afr runs list [--status S] [--tag T] [--limit N]` | run manifest |
| `afr ls [--status S] [--tag T] [--limit N]` | short alias for `afr runs list` |
| `afr runs show <run_id|latest>` | run details + checkpoints + fork lineage |
| `afr show [run_id|latest]` | short alias for `afr runs show` |
| `afr inspect [run_id|latest] [--errors-only] [--calls]` | run summary plus event timeline |
| `afr events <run_id|latest> [--type T] [--errors-only] [--limit N]` | timeline (`✗` marks failures) |
| `afr timeline [run_id|latest]` | short alias for `afr events` |
| `afr calls [run_id|latest]` | model/tool call timeline only |
| `afr replay <run_id|latest> --from <ckpt|latest> [--mode M] [--approved] [--handler module:fn]` | request replay; invoke resume handler unless `dry_run` |
| `afr export <run_id|latest> [-o FILE]` | portable JSON bundle (run + events + checkpoints) |
| `afr case [run_id|latest] [--from <ckpt|latest>] [-o DIR] [--name NAME] [--force]` | create `case.json`, a pytest template, and a README from a checkpoint |
| `afr repair-case [run_id|latest] [--from <ckpt|latest>]` | alias for `afr case` |
| `afr-regression-case <run_id> --from <ckpt> [-o DIR] [--name NAME] [--force]` | compatibility command for regression-case generation |
| `afr fork <run_id> --from <ckpt> [--name N]` | fork a new run from a checkpoint (premium) |
| `afr tag <run_id> TAG... [--remove]` | add/remove run tags (premium) |
| `afr note <run_id> TEXT [--append]` | set run notes (premium) |
| `afr license` | show plan + feature flags |

Replay modes: `dry_run` (default) · `mock_tools` · `allow_safe_tools`† · `allow_side_effects`† († premium; `--approved` unblocks `requires_approval` tools in `allow_side_effects` mode).

## Friendly failure-to-repair spine

```bash
afr demo
afr inspect latest
afr calls latest
afr events latest --errors-only
afr case latest --from latest -o cases/incident-42
```

## Explicit/id-based spine

```bash
afr runs list --status failed
afr runs show 648c2cd9
afr events 648c2cd9 --errors-only
afr replay 648c2cd9 --from dfd2082b                 # dry run, prints state
afr export 648c2cd9 -o incident-42.json
afr-regression-case 648c2cd9 --from dfd2082b -o cases/incident-42
```

Export format: `{"format": "afr.export.v1", "run": ..., "events": [...], "checkpoints": [...]}` — stable, diff-able, safe to attach to a ticket.

Regression-case format: `{"format": "afr.regression_case.v1", "run": ..., "checkpoint": ..., "state": ..., "events": [...]}` — stable fixture for a pytest repair test. It does not replay side effects.
