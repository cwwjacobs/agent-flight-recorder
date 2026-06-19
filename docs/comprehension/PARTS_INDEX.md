# AFR Parts Index

Status: comprehension anchor
Audience: Core / future coding agents

## Rule for every part

Every part must be explainable in five lines:

1. what it is
2. why it exists
3. what it receives
4. what it produces
5. what breaks if it fails

No new code should be added to a part until this five-line shape is clear.

---

## Backend

What it is: FastAPI service for receiving, storing, reading, and replay-preparing AFR runs.

Why it exists: Centralizes run/event storage and exposes HTTP APIs for SDK, CLI, and UI.

Receives: HTTP/JSON requests from SDK, CLI, UI, examples, and scripts.

Produces: persisted runs/events/checkpoints, reconstructed states, replay plans, API responses.

If it fails: nothing reliable can be recorded, inspected, reconstructed, or exported.

---

## SDK

What it is: Python package imported by agent code.

Why it exists: Gives agent code simple hooks/decorators/context managers for recording model calls, tool calls, state, checkpoints, logs, and errors.

Receives: Python function calls, context manager events, tool/model call payloads, state dictionaries.

Produces: structured AFR events sent to the backend.

If it fails: agent behavior may happen without evidence, or evidence may be malformed/incomplete.

---

## Storage

What it is: Local persistence layer, currently SQLite according to the README.

Why it exists: Preserves an append-only timeline that can be inspected later.

Receives: run metadata, events, checkpoints, state snapshots, replay records.

Produces: queryable run/event data for backend/API/CLI/UI/export.

If it fails: recorded history is missing, corrupted, or unreconstructable.

---

## Replay layer

What it is: Logic for reconstructing state at a checkpoint and preparing a replay contract.

Why it exists: Lets Core debug from a safe point without blindly re-running side effects.

Receives: run ID, checkpoint ID, recorded state/events, replay mode, tool policy.

Produces: reconstructed checkpoint state and replay plan/ticket.

If it fails: replay may be unsafe, incorrect, or impossible.

---

## CLI

What it is: Terminal interface for AFR.

Why it exists: Gives Core quick inspection, export, replay, and diagnostic commands without opening the UI.

Receives: user commands such as list runs, inspect events, export, replay, doctor.

Produces: terminal output, exports, replay requests, diagnostic reports.

If it fails: Core loses the fastest path to verify and operate the recorder.

---

## UI

What it is: React/Vite web interface.

Why it exists: Makes run timelines, event payloads, checkpoints, errors, state, and replay plans visible to humans.

Receives: API responses from backend and user clicks/selections.

Produces: visual timeline, state inspector, checkpoint view, replay-plan view.

If it fails: AFR may technically work but feel unusable or untrustworthy.

---

## Examples

What they are: Demo agents and seed scripts.

Why they exist: Prove AFR can record and replay concrete scenarios without needing private projects or API keys.

Receive: demo commands and local runtime.

Produce: sample runs, events, checkpoints, errors, replay cases.

If they fail: Core loses the easiest proof path for understanding and marketplace/demo material.

---

## Docs

What they are: Human-readable explanation, run instructions, APIs, and comprehension anchors.

Why they exist: Make AFR ownable, teachable, and releasable.

Receive: repo truth, operator decisions, proof receipts, known limitations.

Produce: system maps, runbooks, proof notes, onboarding paths.

If they fail: the repo may exist but not converge in Core's head.

---

## Unknown / pending parts

The repo may include additional modules or analysis components not fully mapped here yet. Add each one only after a five-line explanation is written.
