# AFR Data Flow

Status: comprehension anchor
Audience: Core / future coding agents

## One-line flow

```text
agent action -> SDK event -> backend API -> SQLite timeline -> UI/CLI inspection -> checkpoint replay/export proof
```

## Flow as stages

### 1. Agent does work

An AI agent runs normal code: model calls, tool calls, state changes, checkpoints, logs, errors.

AFR should not replace the agent. AFR observes and records the run.

### 2. SDK captures events

The SDK wraps or receives interesting moments:

- model call
- tool call
- state snapshot
- checkpoint
- log
- error

The SDK turns those moments into structured event payloads.

### 3. Backend receives events

The backend accepts HTTP/JSON requests from the SDK, CLI, UI, examples, or scripts.

It validates and routes the data into storage.

### 4. Storage preserves timeline

SQLite stores the run as an append-only event timeline.

The timeline is the source of later inspection and reconstruction.

### 5. UI and CLI read the timeline

The UI shows the run visually.
The CLI shows the run operationally.

Both are readers/operators over the same recorded evidence.

### 6. Checkpoint state can be reconstructed

A checkpoint marks a safe and meaningful point in the run.

Replay logic reconstructs the state as of that checkpoint, then prepares a replay plan.

### 7. Replay is prepared, not blindly executed by the server

The backend prepares a replay contract.

The agent-side resume handler owns actual execution. Tool policy controls whether tools are allowed, mocked, skipped, or blocked.

### 8. Export turns run into proof

An export should preserve enough data to prove what happened:

- run metadata
- event timeline
- checkpoint list
- error context
- replay plan where relevant
- state snapshots or reconstructed state where relevant
- limitations / missing evidence

## Comprehension checkpoints

Core should be able to answer these before more build work:

1. Where does a run begin?
2. What event types exist?
3. Where are events stored?
4. What makes a checkpoint replayable?
5. What does the backend never do during replay?
6. What does the UI need to show for AFR to feel usable?
7. What does an export need to prove?

## Drift check

AFR drifts if it becomes:

- a generic logging app
- a generic dashboard
- an opaque replay engine Core cannot explain
- a pile of feature claims without proof exports
- a UI that hides the run instead of clarifying it

Return to the one-line flow when lost.
