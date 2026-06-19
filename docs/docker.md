# Docker

One image: FastAPI backend + the built web UI, SQLite on a named volume.

```bash
docker compose up --build
# → http://localhost:8700  (UI + API + /docs)
make demo-docker            # seed the demo incident against it
```

Data persists in the `afr-data` volume (`/data/afr.db` inside the container).

## Network exposure (read before deploying)

The compose file publishes **127.0.0.1:8700:8700** — localhost only. (The
server process binds `0.0.0.0` *inside* the container so Docker's port publish
can reach it; host exposure is controlled entirely by that compose `ports`
line.) Recorded prompts, tool args, and state are sensitive, and a fresh
instance has no auth. To expose it beyond the machine, do both, deliberately:

1. set `AFR_API_TOKEN=<long random string>` (bearer or `X-AFR-Token` auth on
   every API route; `/health` stays open), and
2. change the ports line to `"8700:8700"` (or front it with your own proxy/TLS).

Clients then send `Authorization: Bearer <token>` — the SDK/CLI read
`AFR_API_TOKEN` from the environment automatically, and the web UI prompts
for the token and stores it in localStorage.

## Configuration

| Env var | Default (compose) | Meaning |
| --- | --- | --- |
| `AFR_EXPERIMENTAL_FEATURES_ENABLED` | `false` | opt-in advanced/experimental features (local flag, no payment) |
| `AFR_REPLAY_ENABLED` | `true` | prepare replay plans (the server never executes your code) |
| `AFR_REDACTION_ENABLED` | `true` | default key redaction |
| `AFR_REDACT_KEYS` | — | extra comma-separated key substrings |
| `AFR_API_TOKEN` | — (unset = open) | auth for every API endpoint |
| `AFR_CORS_ORIGINS` | local dev origins | comma-separated allowed origins |
| `AFR_DEMO_SEED_ENABLED` | `true` | `false` disables `POST /demo/seed` |
| `AFR_DB_PATH` | `/data/afr.db` | SQLite location |
| `AFR_UI_DIST` | `/app/ui-dist` | built UI directory (set in the image) |

Enable the advanced/experimental features explicitly:
`AFR_EXPERIMENTAL_FEATURES_ENABLED=true docker compose up`. The deprecated
`AFR_PREMIUM_ENABLED` is still honored as an alias.

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
