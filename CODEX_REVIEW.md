# Codex Review Packet

This document is for human review of Agent Flight Recorder (AFR) as a Codex/open-source artifact. It summarizes what the current repository claims, what it does not claim, how to evaluate the runnable path, and how the recent supply-chain containment should be read.

## Short description

AFR is a local-first run recorder for tool-using AI agents. It records the observable boundary of a run: model calls, tool calls, tool results, state snapshots, checkpoints, errors, and replay requests.

The goal is not to expose model internals. The goal is to preserve enough execution evidence that an operator can inspect a failure, reconstruct recorded state, and prepare a replay path with side effects mocked or gated.

## What reviewers should evaluate

Reviewers should evaluate whether the repository provides a coherent, runnable baseline for:

- recording agent run events;
- inspecting recorded timelines;
- storing state snapshots and checkpoint metadata;
- preparing replay tickets or replay plans from checkpoints;
- keeping replay execution outside the backend;
- documenting local-first security boundaries;
- handling sensitive payloads with clear redaction limits.

## What works in the current baseline

The current baseline is intended to support:

- a FastAPI backend;
- local SQLite-backed storage;
- Python SDK recording helpers;
- CLI inspection paths;
- example/demo run seeding;
- replay ticket generation;
- side-effect-aware replay modes such as dry run and mocked tools;
- localhost-first Docker backend execution.

The Docker path is backend-first. It binds to `127.0.0.1:8700` by default and stores the database in a Docker volume.

## What AFR does not claim

AFR does not claim to recover or expose:

- hidden chain-of-thought;
- private model reasoning;
- neural activations;
- model intent;
- training traces;
- a complete record of state that was never logged.

AFR is not an enterprise security product, not a sandbox by itself, and not a guarantee that sensitive data was never recorded. Redaction is best-effort and should be treated as a reduction layer, not a proof of safety.

## Replay boundary

Replay is deliberately split:

- The backend owns recorded history, state reconstruction from recorded events, and replay ticket generation.
- The backend does not execute user code.
- A user-provided resume handler owns replay execution.
- The SDK provides helpers for honoring mock, skip, block, and allow decisions.

A resume handler that bypasses those helpers can bypass AFR's replay policy. That is a boundary, not a hidden guarantee.

## Supply-chain containment note

A prior active install/build surface included an unverified dependency path named `httpx2`. This was treated as a dependency-confusion or supply-chain risk, not as confirmed malware.

Containment work removed the risky active dependency surface, quarantined legacy UI/build exposure, made the Docker path backend-first, removed external Google Fonts loads, and preserved older MVP state for review. No confirmed malware was found.

Reviewers should treat the current backend-first Docker path as the primary runnable evaluation path. UI source may exist in the repository, but UI build surfaces should be reviewed separately before being treated as part of the trusted demo path.

## Suggested review path

```bash
docker compose up --build
make demo-docker
```

Then inspect the backend, seeded demo data, CLI/API behavior, replay ticket behavior, and documentation consistency.

For no-Docker local development:

```bash
make install
make serve
make demo
afr doctor
```

## Reviewer-safe summary

AFR is a usable OSS baseline for local agent run recording and replay planning. Its value is practical observability of the agent execution boundary, not interpretability of model internals. The current reviewer path should be treated as backend-first and containment-aware.
