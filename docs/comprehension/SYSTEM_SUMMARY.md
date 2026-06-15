# AFR System Summary

Status: comprehension anchor
Audience: Core / future coding agents

## One-breath summary

Agent Flight Recorder records AI-agent work sessions so the run can be inspected, replayed from checkpoints, audited, and exported as proof.

## What AFR is

AFR is an agent debugging and proof-recording system.

It turns an agent run into a structured timeline:

1. record model calls, tool calls, state snapshots, checkpoints, logs, and errors
2. store them in an append-only local timeline
3. inspect them through CLI or web UI
4. reconstruct state at checkpoints
5. prepare replay plans without the server executing user code
6. export the run as evidence

## What AFR is not

AFR is not the agent.
AFR is not the model.
AFR is not a cloud service requirement.
AFR is not a magic auto-fixer.
AFR is not useful if Core cannot explain what it captured and why it matters.

## Sum and parts

The sum:

> AFR is the black box for an AI agent run.

The parts:

| Part | Purpose |
|---|---|
| SDK | Lets Python agent code record events into AFR. |
| Backend | Receives events, stores runs, reconstructs state, prepares replay plans. |
| Storage | Preserves the append-only timeline in SQLite. |
| Replay layer | Reconstructs checkpoint state and creates a safe replay contract. |
| CLI | Lets Core inspect, export, replay, and diagnose from terminal. |
| UI | Lets Core see the timeline, state, checkpoints, errors, and replay plan visually. |
| Examples | Prove the system can record and replay a demo agent. |
| Docs | Make the system understandable, usable, and ownable. |

## Current comprehension rule

Before any feature expansion, Core should be able to say:

```text
AFR receives agent events, stores them as a run timeline, lets me inspect the run, reconstructs checkpoint state, and prepares replay/export artifacts so the session becomes usable proof.
```

If that sentence feels fuzzy, return to the map before building.

## Why this file exists

This file is the sum-level anchor. It exists so Core can reconnect to the whole system later, even after months away.
