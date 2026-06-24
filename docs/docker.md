# Docker

The current Dockerfile is a legacy packaging path that builds the FastAPI backend plus the preserved legacy UI. AFR v0.2 itself is CLI-first; Docker is not required for recording, inspecting, exporting, replay-ticket generation, or regression-case generation.

```bash
docker compose up --build
# → http://localhost:8700  (API + /docs; any served UI is legacy)
make demo-docker            # seed the demo incident against it
```

Data persists in the `afr-data` volume (`/data/afr.db` inside the container).

## Network exposure (read before deploying)

The compose file binds **127.0.0.1:8700:8700** — localhost only. Recorded
prompts, tool args, and state are sensitive, and a fresh instance has no
auth. To expose it beyond the machine, do both, deliberately:

1. set `AFR_API_TOKEN=<long random string>` (bearer or `X-AFR-Token` auth on
   every API route; `/health` stays open), and
2. change the ports line to `"8700:8700"` (or front it with your own proxy/TLS).

Clients then send `Authorization: Bearer <token>` — the SDK/CLI read
`AFR_API_TOKEN` from the environment automatically.

## Configuration

| Env var | Default (compose) | Meaning |
| --- | --- | --- |
| `AFR_PREMIUM_ENABLED` | `false` | opt-in license placeholder toggle |
| `AFR_REDACTION_ENABLED` | `true` | default key redaction |
| `AFR_REDACT_KEYS` | — | extra comma-separated key substrings |
| `AFR_API_TOKEN` | — (unset = open) | auth for every API endpoint |
| `AFR_CORS_ORIGINS` | local dev origins | comma-separated allowed origins |
| `AFR_DEMO_SEED_ENABLED` | `true` | `false` disables `POST /demo/seed` |
| `AFR_DB_PATH` | `/data/afr.db` | SQLite location |
| `AFR_UI_DIST` | `/app/ui-dist` | legacy built UI directory |

Enable the premium placeholder explicitly:
`AFR_PREMIUM_ENABLED=true docker compose up`.

## Recording from the host

The SDK defaults to `http://127.0.0.1:8700`, which matches the published
port:

```bash
AFR_API_URL=http://127.0.0.1:8700 python examples/toy_agent/toy_agent.py
```

## Notes

- The image does not include the SDK/CLI/examples — it's the server. Install
  `afr-sdk`/`afr-cli` in whatever environment your agent runs in.
- Backups: stop the stack and copy the volume, or just copy `afr.db*` files.
