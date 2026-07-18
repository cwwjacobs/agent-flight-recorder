# Agent Flight Recorder v0.2.0

**Release scope:** public, local-first OSS baseline for recording and inspecting observable evidence from tool-using agent runs.

## What ships

- FastAPI backend with SQLite-first local storage
- Python SDK for recording model calls, tool calls, tool results, state snapshots, checkpoints, errors, and replay requests
- `afr` command-line interface for listing, inspecting, and exporting recorded runs
- regression-case generation from recorded checkpoints
- replay planning with explicit feature gating and side-effect policy choices
- Docker and non-Docker quickstart paths
- LangChain / LangGraph callback integration path
- bounded public eval seed records
- Apache-2.0 license, claim contract, and public-claim CI guardrail

## Start here

```bash
docker compose up --build
make demo-docker
afr runs list --status failed
```

Or without Docker:

```bash
make install
make serve
make demo
afr doctor
afr runs list
```

## Core workflow

```text
record -> inspect -> export -> regression case -> eval seed
```

Representative commands:

```bash
afr events <RUN_ID> --errors-only
afr export <RUN_ID> -o incident.json
afr-regression-case <RUN_ID> --from <CHECKPOINT_ID> -o cases/demo-repair
```

## Claim boundary

AFR records execution evidence supplied through its SDK, API, CLI, or adapter path. It does not expose hidden model reasoning, recover true internal intent, guarantee complete state capture, or provide a sandbox by itself.

Replay is disabled by default. The server prepares replay tickets and plans; user-provided resume handlers own execution and must honor mock, skip, block, and allow decisions.

Recorded prompts, tool payloads, results, and state can contain sensitive information. Redaction is best-effort. The backend binds to loopback by default, and non-loopback use requires deliberate authentication and deployment controls.

## Release verification

The release candidate is accepted only when GitHub CI passes both:

1. the public-claim sanity check; and
2. the Python backend test suite on Python 3.12.

The legacy UI build remains intentionally quarantined and is not part of v0.2.0.

## Package versions

- `afr-sdk`: `0.2.0`
- `afr-cli`: `0.2.0`

## License

Apache License 2.0. Copyright 2026 Terminus Protocol.
