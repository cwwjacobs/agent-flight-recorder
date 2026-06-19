# Quickstart

The fastest path is Docker + the seeded demo:

```bash
docker compose up --build      # backend + UI on http://127.0.0.1:8700
make demo-docker               # seed checkout-agent-payment-timeout
open http://127.0.0.1:8700
```

The Docker image builds the web UI and serves it from the FastAPI backend. Data is stored in a local Docker volume.

Everything below is the no-Docker path.

## 1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install --constraint backend/requirements.txt -e ./sdk -e ./cli -e './backend[dev]'
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
.venv/bin/python examples/toy_agent/toy_agent.py            # or: make demo
.venv/bin/python examples/langchain_like_agent/agent.py     # or: make demo-langchain
python3 scripts/seed_demo_run.py                            # or: make demo-docker
```

The toy agent records model calls, tool calls (one fails on purpose and is retried), state snapshots, and three checkpoints. The langchain-like agent records through the adapter ([integrations.md](integrations.md)). The seed script creates the polished `checkout-agent-payment-timeout` incident.

Something not working?

```bash
.venv/bin/afr doctor    # backend reachable? auth? can it write?
```

## 4. Inspect

CLI:

```bash
.venv/bin/afr runs list
.venv/bin/afr runs show <run_id>      # ids accept unique prefixes (8 chars)
.venv/bin/afr events <run_id>
```

Web UI (dev mode, hot reload):

```bash
cd ui && npm install && npm run dev    # http://127.0.0.1:5173 (proxies /api to :8700)
```

Web UI (production, served by the backend):

```bash
cd ui && npm install && npm run build  # backend now serves it at http://127.0.0.1:8700
```

## 5. Replay from a checkpoint

Replay is deliberately disabled by default. Enable it only when you are ready to request replay tickets or invoke resume handlers.

Docker:

```bash
AFR_REPLAY_ENABLED=true docker compose up --build
AFR_REPLAY_ENABLED=true .venv/bin/afr replay <run_id> --from <checkpoint_id>
AFR_REPLAY_ENABLED=true .venv/bin/afr replay <run_id> --from <checkpoint_id> \
    --mode mock_tools --handler examples.toy_agent.replay_handler:resume
```

No Docker:

```bash
AFR_REPLAY_ENABLED=true make serve
AFR_REPLAY_ENABLED=true .venv/bin/afr replay <run_id> --from <checkpoint_id>
AFR_REPLAY_ENABLED=true .venv/bin/afr replay <run_id> --from <checkpoint_id> \
    --mode mock_tools --handler examples.toy_agent.replay_handler:resume
```

Use `PYTHONPATH=.` from the repo root so the example handler module resolves.

## 6. Point your own agent at it

```python
import afr

with afr.start_run("my-agent"):
    afr.log_model(model="gpt-x", input="...", output="...")
    afr.log_state({"step": 1})
    afr.checkpoint("step-1")
```

Set `AFR_API_URL` if the backend is not on `http://127.0.0.1:8700`, or run `afr init` to write a per-project `.afr/config.json`. If the server was started with `AFR_API_TOKEN`, export the same variable where your agent and CLI run. The SDK sends it automatically.
