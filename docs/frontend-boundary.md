# Frontend Boundary

AFR is CLI-first, local-first, and text-first.

AFR does not use React, Vite, Next, Vue, Svelte, or npm-based application frameworks for core functionality.

Allowed user-facing surfaces:

- CLI commands
- terminal TUI
- markdown reports
- JSON / JSONL exports
- plain static HTML generated from trusted local data

No frontend dependency graph may become required for recording, inspecting, exporting, replay-ticket generation, or regression-case generation.

The legacy UI path is not part of AFR v0.2.

AFR v0.2 is the CLI Visibility Cut.
