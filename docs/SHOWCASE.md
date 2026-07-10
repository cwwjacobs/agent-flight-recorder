# Agent Flight Recorder showcase guide

## One-line portfolio description

Agent Flight Recorder is a local-first evidence layer for tool-using AI agents. It records model calls, tool calls, tool results, state snapshots, checkpoints, and errors, then turns failed runs into portable incident bundles, replay plans, regression fixtures, and eval seeds.

## Why this project belongs in a portfolio

AFR demonstrates an end-to-end agent observability system rather than a thin interface around a model API:

- FastAPI backend with SQLite-first local storage
- Python SDK and CLI
- Docker and non-Docker startup paths
- append-only run evidence
- checkpoint inspection and side-effect-aware replay planning
- regression-case generation
- LangChain and LangGraph integration path
- public CI, smoke tests, documentation, and Apache-2.0 licensing

## 90-second demo

```bash
docker compose up --build
make demo-docker
afr runs list --status failed
afr events <RUN_ID> --errors-only
afr export <RUN_ID> -o incident.json
afr-regression-case <RUN_ID> --from <CHECKPOINT_ID> -o cases/demo-repair
```

Show these moments in order:

1. A failed run appears in the run list.
2. The error event and surrounding tool evidence are visible.
3. The run exports to a portable JSON incident bundle.
4. A selected checkpoint becomes a pytest-oriented regression case.
5. Replay remains disabled until explicitly enabled.

## Screenshot and recording shot list

Capture at 1440p or higher:

1. terminal with `afr runs list --status failed`
2. terminal with the error-only event timeline
3. exported incident JSON opened in a structured viewer
4. generated regression-case folder showing `case.json`, README, and pytest template
5. architecture crop showing `backend/`, `sdk/`, `cli/`, `examples/`, and `evals/`

Avoid screenshots containing real prompts, credentials, customer data, or unredacted tool payloads.

## Proof points to mention

- local loopback binding by default
- explicit replay feature gate
- side-effect policy choices: mock, skip, block, or allow
- portable export and reproducible regression artifacts
- bounded claims: AFR records observable execution evidence, not hidden reasoning

## Honest boundaries

AFR is not a sandbox, model-interpretability system, or guarantee that every state transition was captured. Redaction is best-effort. Replay execution belongs to a user-provided resume handler and must honor the generated policy plan.

## Suggested GitHub description

> Local-first recorder, replay planner, and regression-case generator for tool-using AI agent runs.

## Suggested topics

`ai-agents` `agent-observability` `agent-debugging` `replay` `fastapi` `python` `sqlite` `local-first` `evals`

## Suggested pinned-repository caption

> Inspect what an agent received, called, returned, and recorded before a failure, then turn the evidence into a safe regression case.
