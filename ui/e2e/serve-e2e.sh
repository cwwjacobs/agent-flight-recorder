#!/usr/bin/env bash
# Seed a fresh >10k-event database and serve the backend (with the built UI
# from ui/dist) for the Playwright journey. Invoked by playwright's webServer.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${AFR_E2E_PYTHON:-$REPO_ROOT/.venv/bin/python}"
PORT="${AFR_E2E_PORT:-8791}"

export AFR_DB_PATH="$REPO_ROOT/ui/e2e/.e2e-afr.db"
export AFR_REPLAY_ENABLED=true

rm -f "$AFR_DB_PATH" "$AFR_DB_PATH-wal" "$AFR_DB_PATH-shm"

PYTHONPATH="$REPO_ROOT/backend" "$PY" "$REPO_ROOT/ui/e2e/seed_run.py" \
  > "$REPO_ROOT/ui/e2e/.seed.json"

cd "$REPO_ROOT/backend"
exec "$PY" -m app --port "$PORT"
