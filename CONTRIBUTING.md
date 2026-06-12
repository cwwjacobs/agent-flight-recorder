# Contributing

Thanks for looking. The bar here is *boring, working code with honest docs* —
explicit stubs over silent fakes, tests over promises.

## Setup

```bash
make install     # venv + backend/sdk/cli editable installs
make test        # full Python suite (must pass before any PR)
make serve       # backend on http://127.0.0.1:8700
cd ui && npm ci && npm run dev   # UI dev server with /api proxy
```

`afr doctor` diagnoses a broken setup faster than you can.

## Ground rules

- **Tests come with the change.** Backend/SDK/CLI behavior changes need a
  test in `backend/tests/` (the suite drives the SDK and CLI against an
  in-process app — no sockets, see `conftest.py`).
- **Events are append-only.** No UPDATE/DELETE paths on the events table.
- **State folds by `seq`,** never timestamps.
- **Redaction is not a feature tier.** Default secret scrubbing stays free.
- **Don't overclaim in docs or UI copy.** The server prepares replay plans;
  it never executes user code — keep that wording exact.
- **Preserve the MVP snapshot** under `dist/mvp-agent-flight-recorder/`.
- CI runs Python 3.12 tests + a Node 20 UI build on every PR; both must be
  green.

## Good first contributions

Framework adapters (OpenAI Agents SDK, CrewAI) following the pattern in
`sdk/afr/integrations/langchain.py` — optional dependency, import-safe,
duck-typed, tested with fake payloads. See `docs/roadmap.md`.
