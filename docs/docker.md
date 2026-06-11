# Docker

One image: FastAPI backend + the built web UI, SQLite on a named volume.

```bash
docker compose up --build
# → http://localhost:8700  (UI + API + /docs)
```

Data persists in the `afr-data` volume (`/data/afr.db` inside the container).

## Configuration

| Env var | Default (compose) | Meaning |
| --- | --- | --- |
| `AFR_PREMIUM_ENABLED` | `true` | license placeholder toggle |
| `AFR_REDACTION_ENABLED` | `true` | default key redaction |
| `AFR_REDACT_KEYS` | — | extra comma-separated key substrings |
| `AFR_DB_PATH` | `/data/afr.db` | SQLite location |
| `AFR_UI_DIST` | `/app/ui-dist` | built UI directory |

Try the free tier: `AFR_PREMIUM_ENABLED=false docker compose up`.

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
