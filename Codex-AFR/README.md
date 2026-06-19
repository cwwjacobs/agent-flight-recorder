# Codex-AFR

A first-class capture layer for [OpenAI Codex](https://github.com/openai/codex) in the Agent Flight Recorder (AFR) project.

## Scripts

| Script | Purpose |
|--------|---------|
| `codexafr` | Main wrapper that launches Codex and streams events/checkpoints to AFR |
| `codexafr-hook-bridge.py` | Receives Codex hook events and forwards them to the launcher |
| `codexafr-api-proxy` | OpenAI-compatible API proxy used by `--api-key` mode |
| `codexafr-harness` | Convenience harness: starts AFR if needed, runs `codexafr`, captures output tail, and packages the run |
| `afr-add-codex-output` | Idempotently append a `codex_output_tail` event to a completed run |
| `afr-package-latest-codex` | Export the latest completed Codex run and build a sanitized share package |
| `smoke-codex-package.sh` | End-to-end smoke test using a fake Codex binary and a temp backend |

## Quick start

```bash
# Account-login mode (default). Uses Codex hooks; no API key required.
./Codex-AFR/codexafr-harness

# API-key mode. Requires OPENAI_API_KEY; traffic is routed through a local proxy.
OPENAI_API_KEY="sk-..." ./Codex-AFR/codexafr-harness --api-key
```

## Modes

### Account-login mode (default)

`codexafr` locates the `codex` binary, creates a temporary `CODEX_HOME` directory, copies/symlinks any existing `~/.codex/auth.json` so account login still works, and writes a `config.toml` that registers Codex hooks:

- `SessionStart`
- `PostToolUse`
- `AfterAgent`
- `Stop`

The hooks point at `codexafr-hook-bridge.py`, which posts structured events to a small local HTTP receiver started by the launcher. Because Codex itself handles authentication via the user's saved account session, no `OPENAI_API_KEY` is needed.

> **Codex version note:** The hooks config format has changed across Codex releases. `codexafr` writes the inline TOML format documented for current Codex versions. If you see a config load error on startup, set `CODEX_AFR_DEBUG=1` and check the generated `config.toml` under the temp `CODEX_HOME` shown in the output.

### `--api-key` mode

When `--api-key` is passed, `codexafr` starts `codexafr-api-proxy` as a child process, sets `OPENAI_BASE_URL` to the proxy URL, and runs Codex. The proxy forwards requests to `https://api.openai.com` (or `OPENAI_API_BASE`) using `OPENAI_API_KEY`. It emits `model_call`, `tool_call`, and `tool_result` events directly to AFR.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODEX_BIN` | auto-detected | Path to the `codex` executable |
| `AFR_API_URL` | `http://127.0.0.1:8700` | AFR API base URL |
| `AFR_API_TOKEN` | none | AFR auth token |
| `AFR_ROOT` | repo root | Directory used for `.afr/`, `exports/`, and `share/` |
| `OPENAI_API_KEY` | none | Required in `--api-key` mode |
| `OPENAI_API_BASE` | `https://api.openai.com` | Upstream API base used by the proxy |

## File layout

```text
Codex-AFR/
├── codexafr                       # launcher wrapper
├── codexafr-hook-bridge.py        # Codex hook bridge
├── codexafr-api-proxy             # OpenAI API proxy
├── codexafr-harness               # convenience harness
├── afr-add-codex-output           # output-tail helper
├── afr-package-latest-codex       # packaging helper
├── smoke-codex-package.sh         # smoke test
├── .afr/codex/{run_id}/           # transcripts and run-local files
├── exports/codex-trace-{prefix}.json
└── share/codex-clean-{prefix}/    # sanitized share package (redacted export + receipt by default)
```

## Smoke test

```bash
./Codex-AFR/smoke-codex-package.sh
```

The smoke test uses a fake `codex` binary and a throwaway backend database to verify:

- `codex_output_tail` event is recorded
- idempotency of `afr-add-codex-output`
- default sanitized package tarball contains only the redacted export and receipt
- `--include-raw-transcript` produces a redacted transcript copy
- obvious secrets (`OPENAI_API_KEY`, `Bearer` tokens, cookies, private keys, `auth.json`) are redacted
- receipt fields are correct and `raw_transcript_is_sensitive: true`
- failed runs and stale transcript folders are excluded

## Syntax checks

```bash
# Python executables: use py_compile (do not run bash -n on Python scripts).
python -m py_compile Codex-AFR/codexafr Codex-AFR/codexafr-api-proxy Codex-AFR/afr-add-codex-output Codex-AFR/afr-package-latest-codex Codex-AFR/codexafr-hook-bridge.py

# Bash scripts: use bash -n.
bash -n Codex-AFR/codexafr-harness Codex-AFR/smoke-codex-package.sh
```
