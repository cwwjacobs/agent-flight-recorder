# Quickstart

## 1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e ./sdk -e ./cli -e './backend[dev]'
# or: make install
```

## 2. Start the backend

```bash
cd backend && ../.venv/bin/python -m app          # http://127.0.0.1:8700
# or: make serve
# or: uvicorn app.main:app --app-dir backend --port 8700
```

The SQLite database defaults to `./afr.db` (override with `AFR_DB_PATH`).

## 3. Record a run

```bash
.venv/bin/python examples/toy_agent/toy_agent.py   # or: make demo
```

The toy agent records model calls, tool calls (one fails on purpose and is
retried), state snapshots, and three checkpoints.

## 4. Inspect

CLI:

```bash
.venv/bin/afr runs list
.venv/bin/afr runs show <run_id>      # ids accept unique prefixes (8 chars)
.venv/bin/afr events <run_id>
```

Web UI (dev mode, hot reload):

```bash
cd ui && npm install && npm run dev    # http://127.0.0.1:5173 (proxies /api → :8700)
```

Web UI (production, served by the backend):

```bash
cd ui && npm install && npm run build  # backend now serves it at http://127.0.0.1:8700
```

## 5. Replay from a checkpoint

```bash
.venv/bin/afr replay <run_id> --from <checkpoint_id>                 # dry run: prints state
.venv/bin/afr replay <run_id> --from <checkpoint_id> \
    --mode mock_tools --handler examples.toy_agent.replay_handler:resume
```

(Use `PYTHONPATH=.` from the repo root so the example handler module resolves.)

## 6. Point your own agent at it

```python
import afr

with afr.start_run("my-agent"):
    afr.log_model(model="gpt-x", input="...", output="...")
    afr.log_state({"step": 1})
    afr.checkpoint("step-1")
```

Set `AFR_API_URL` if the backend is not on `http://127.0.0.1:8700`, or run
`afr init` to write a per-project `.afr/config.json`.
