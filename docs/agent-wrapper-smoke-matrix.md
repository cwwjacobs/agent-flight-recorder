# Agent wrapper smoke matrix

This document is a plan. The only implemented wrapper is **Kimi Code**;
Grok, Claude, Codex, and Gemini wrappers are planned but not built yet.

## Planned wrappers

| Wrapper | Binary path | Activation condition |
|---------|-------------|----------------------|
| Kimi Code | `/home/terminus-protocol/.kimi-code/bin/kimi` | Always supported; default path checked first. |
| Grok | `/home/terminus-protocol/.grok/bin/grok` | Activate only if the binary exists. |
| Claude | `claude` on `PATH` | Activate only if `claude` is on `PATH`. |
| Codex | `codex` on `PATH` | Activate only if `codex` is on `PATH` or a fixed install path is configured later. |
| Gemini | `gemini` on `PATH` | Activate only if `gemini` is on `PATH`. |

## Smoke requirements for every wrapper

Each wrapper must pass a smoke test equivalent to `scripts/smoke-kimi-package.sh`:

1. **Fake binary mode**  
   The smoke test must be able to point the wrapper at a fake binary that
   prints known output and exits cleanly, so no real API credits are spent.

2. **Transcript capture**  
   The wrapper must record a terminal transcript (via `script` or a fallback
   pipe) and write it under `.afr/<agent>/<run_id>/terminal-transcript.txt`.

3. **Exit code capture**  
   The wrapper must record the wrapped agent's exit code and mark the AFR run
   as `completed` on success or `failed` on non-zero exit.

4. **Output-tail event**  
   After a successful run, the wrapper or a companion helper must add an
   `<agent>_output_tail` log event containing a tail of the transcript.

5. **Clean package**  
   A packaging script must build a tarball containing exactly:
   - `<agent>-clean-<prefix>/`
   - `<agent>-clean-<prefix>/<agent>-trace-<prefix>.json`
   - `<agent>-clean-<prefix>/receipt.json`
   - `<agent>-clean-<prefix>/terminal-transcript.txt`

6. **Stale session exclusion**  
   Failed, running, and stale sessions must be excluded from the package. The
   package helper must consider only completed runs with matching agent
   metadata.

7. **No real credits required during smoke**  
   The smoke test must complete using only local tools and a throwaway AFR
   backend. No calls to the real agent API are permitted.

## Status

- Kimi Code: implemented and covered by `scripts/smoke-kimi-package.sh`.
- Grok: planned, pending wrapper implementation.
- Claude: planned, pending wrapper implementation.
- Codex: planned, pending wrapper implementation.
- Gemini: planned, pending wrapper implementation.
