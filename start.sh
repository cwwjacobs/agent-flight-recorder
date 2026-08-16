#!/usr/bin/env sh
set -eu

URL="http://127.0.0.1:8700"
OPEN_BROWSER=true

if [ "${1:-}" = "--no-browser" ]; then
  OPEN_BROWSER=false
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop, then run this script again." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is required. Update Docker Desktop, then run this script again." >&2
  exit 1
fi

echo "Building and starting Agent Flight Recorder..."
docker compose up --build -d

container_id="$(docker compose ps -q afr)"
if [ -z "$container_id" ]; then
  echo "AFR did not create a container. Run 'docker compose logs afr' for details." >&2
  exit 1
fi

attempt=0
status="starting"
while [ "$attempt" -lt 90 ]; do
  attempt=$((attempt + 1))
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
  case "$status" in
    healthy)
      break
      ;;
    unhealthy|exited|dead)
      echo "AFR failed to become healthy (status: $status)." >&2
      docker compose logs afr >&2
      exit 1
      ;;
  esac
  sleep 1
done

if [ "$status" != "healthy" ]; then
  echo "AFR did not become healthy before the startup deadline." >&2
  docker compose logs afr >&2
  exit 1
fi

echo "Agent Flight Recorder is ready at $URL"
echo "Data is stored in the Docker volume named afr-data."
echo "Stop it with: docker compose down"

if [ "$OPEN_BROWSER" = true ]; then
  if command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  else
    echo "Open $URL in your browser."
  fi
fi
