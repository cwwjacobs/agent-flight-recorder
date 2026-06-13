# Development

Agent Flight Recorder is **proprietary software** — see `LICENSE`. This file is
for the owner and any authorized contractors or licensees; it is **not** an
invitation for public contributions. Licensing and commercial inquiries:
https://terminusprotocol.io

## Setup

```bash
make install     # venv + backend/sdk/cli editable installs
make test        # full Python suite (must pass before any change lands)
make serve       # backend on http://127.0.0.1:8700
cd ui && npm ci && npm run dev   # UI dev server with /api proxy
```

`afr doctor` diagnoses a broken setup faster than you can.

## Engineering invariants (do not break)

- **Tests come with the change.** Backend/SDK/CLI behavior changes need a test
  in `backend/tests/` (the suite drives the SDK and CLI against an in-process
  app — no sockets, see `conftest.py`).
- **Events are append-only.** No UPDATE/DELETE paths on the events table.
- **State folds by `seq`,** never timestamps.
- **Redaction is not a feature tier.** Default secret scrubbing — sensitive
  keys plus common secret shapes in free-text values — stays in every build.
- **Don't overclaim in docs or UI copy.** The server prepares replay plans; it
  never executes user code — keep that wording exact.
- **Preserve the MVP snapshot** under `dist/mvp-agent-flight-recorder/`.
