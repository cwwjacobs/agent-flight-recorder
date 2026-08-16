# Quickstart

## Recommended: download and run with Docker Desktop

The complete Docker image includes the browser UI, backend, SDK, and CLI. No host Python or Node installation is required.

After downloading and extracting the repository or portable ZIP:

**Windows**

```text
double-click start.cmd
```

**macOS or Linux**

```bash
sh start.sh
```

The launcher builds the image, waits for the backend health check, and opens:

```text
http://127.0.0.1:8700
```

The direct command is:

```bash
docker compose up --build
```

The browser empty state can create the `checkout-agent-payment-timeout` demo incident with one click. The same operations are available through the bundled CLI:

```bash
docker compose exec afr afr doctor
docker compose exec afr afr demo
docker compose exec afr afr runs list
docker compose exec afr afr runs show latest
```

Data is stored in the named Docker volume `afr-data`.

```bash
docker compose down       # stop, preserve data
docker compose down -v    # stop and delete data
```

## Local contributor path

Use this path when Python 3.10+ and Node are already installed.

### 1. Install Python packages

```bash
python3 -m venv .venv
.venv/bin/pip install --constraint backend/requirements.txt -e ./sdk -e ./cli -e './backend[dev]'
# or: make install
```

### 2. Build and serve the UI

```bash
make build-ui
make serve                 # API + built UI on http://127.0.0.1:8700
# or: make run             # build-ui followed by serve
```

For UI development, keep `make serve` running and use the Vite proxy:

```bash
cd ui
npm ci
npm run dev                # http://127.0.0.1:5173
```

The SQLite database defaults to `./afr.db`; override it with `AFR_DB_PATH`.

### 3. Record a run

```bash
.venv/bin/python examples/toy_agent/toy_agent.py            # or: make demo
.venv/bin/python examples/langchain_like_agent/agent.py     # or: make demo-langchain
python3 scripts/seed_demo_run.py                            # or: make demo-docker
```

The toy agent records model calls, tool calls, a deliberate failure and retry, state snapshots, and checkpoints. The LangChain-like agent records through the adapter described in [integrations.md](integrations.md).

Something not working?

```bash
.venv/bin/afr doctor
```

### 4. Inspect and export

Use the browser or the CLI:

```bash
.venv/bin/afr runs list
.venv/bin/afr runs show <run_id>      # IDs accept unique prefixes
.venv/bin/afr events <run_id>
.venv/bin/afr events <run_id> --errors-only
.venv/bin/afr export <run_id> -o incident.json
.venv/bin/afr-regression-case <run_id> --from <checkpoint_id> -o cases/incident-42
```

The run detail page also downloads an `*.afr.json` bundle containing the run, events, and checkpoints already loaded in the browser.

### 5. Replay from a checkpoint

Replay is deliberately disabled by default. Enable it only when you are ready to request replay tickets or invoke resume handlers.

Docker:

```bash
AFR_REPLAY_ENABLED=true docker compose up --build
```

Local Python:

```bash
AFR_REPLAY_ENABLED=true make serve
AFR_REPLAY_ENABLED=true .venv/bin/afr replay <run_id> --from <checkpoint_id>
AFR_REPLAY_ENABLED=true .venv/bin/afr replay <run_id> --from <checkpoint_id> \
    --mode mock_tools --handler examples.toy_agent.replay_handler:resume
```

Use `PYTHONPATH=.` from the repository root so an example handler module resolves.

### 6. Point your own agent at AFR

```python
import afr

with afr.start_run("my-agent"):
    afr.log_model(model="gpt-x", input="...", output="...")
    afr.log_state({"step": 1})
    afr.checkpoint("step-1")
```

Set `AFR_API_URL` if the backend is not on `http://127.0.0.1:8700`, or run `afr init` to write a per-project `.afr/config.json`. If the server was started with `AFR_API_TOKEN`, export the same value where the agent and CLI run. The SDK sends it automatically.

See [dependency-map.md](dependency-map.md) for the complete runtime, build, storage, and delivery graph.
