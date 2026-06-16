# Contributing

Thanks for looking at Agent Flight Recorder. The bar is simple: boring, working code with honest docs. Prefer explicit stubs over silent fakes, tests over promises, and narrow changes over broad rewrites.

## Setup

```bash
make install     # venv + backend/sdk/cli editable installs
make test        # full Python suite
make serve       # backend on http://127.0.0.1:8700
cd ui && npm ci && npm run dev   # UI dev server with /api proxy
```

`afr doctor` diagnoses a broken setup faster than manual guessing.

## Engineering invariants

- **Tests come with behavior changes.** Backend/SDK/CLI changes should include or update tests in `backend/tests/`.
- **Events are append-only.** Do not add UPDATE/DELETE paths on the events table.
- **State folds by `seq`,** never timestamps.
- **Redaction is not a feature tier.** Default secret scrubbing stays available in the open-source build.
- **Do not overclaim replay safety.** The server prepares replay plans and reconstructs state; it does not execute user code.
- **Preserve the MVP snapshot** under `dist/mvp-agent-flight-recorder/`.

## Good first contribution lanes

- Framework adapters following the pattern in `sdk/afr/integrations/`.
- Replay-policy tests.
- Docs examples that show safe replay and side-effect mocking.
- CLI usability improvements.
- Redaction test cases.

## License

By contributing, you agree that your contribution is provided under the repository's MIT License. Copyright and attribution notices should preserve Terminus Protocol attribution where applicable.
