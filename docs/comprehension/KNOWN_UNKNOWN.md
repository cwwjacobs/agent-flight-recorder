# AFR Known Unknowns

Status: comprehension anchor
Audience: Core / future coding agents

## Purpose

This file tracks what Core does not fully understand yet.

This is not a defect list. It is a convergence map.

A known unknown is better than fog.

## Current known unknowns

### UI usability

Question: What exactly makes the current UI feel bad or unusable?

Need to inspect:

- run list layout
- run detail layout
- timeline readability
- event payload expansion
- checkpoint selection
- replay plan display
- theme polish
- empty/error/loading states

Resolution path:

1. screenshot current UI
2. write pain points
3. fix one path at a time
4. rerun demo
5. compare before/after

---

### Feature boundary (resolved)

Question: What is always on, what is opt-in, and what backs that split?

Resolved: AFR is fully MIT-licensed and free — there is no commercial tier. Most of
the product is always on. A small set of advanced/experimental features (state
diff, forked replay, advanced replay modes, custom redactors, tags/notes, the
MCP-shaped HTTP prototype) are off by default and enabled with one local flag
(`AFR_EXPERIMENTAL_FEATURES_ENABLED`). The whole gate lives in
`backend/app/license.py`; a disabled feature returns `403`
`experimental_feature_disabled`. See [../features.md](../features.md) for the
table.

---

### Replay mental model

Question: What exactly happens when replay is prepared?

Need to inspect:

- checkpoint state reconstruction
- replay ticket/plan creation
- resume handler contract
- tool policies: allow, mock, skip, block
- what the backend never executes

Resolution path:

1. run demo incident
2. select checkpoint
3. prepare replay plan
4. inspect response
5. explain in five lines

---

### Capture path

Question: How does an agent event travel from Python code into the stored timeline?

Need to inspect:

- SDK decorators/context manager
- HTTP client
- backend API endpoint
- storage write path
- event schema

Resolution path:

1. record one tiny toy run
2. inspect raw stored event
3. inspect API output
4. inspect UI output
5. compare all three views

---

### Export proof shape

Question: What makes an AFR export good enough as proof?

Need to inspect:

- export command output
- included metadata
- included events
- included checkpoints
- hashes/checksums, if any
- limitations/missing data

Resolution path:

1. export demo run
2. read exported file
3. write proof criteria
4. add missing proof fields only if necessary

---

## Agent instruction

Before touching an unknown, answer:

```text
What part is unknown?
What file/path likely owns it?
What command or UI action proves it?
What is the smallest safe inspection step?
What would count as resolved?
```

## Close condition

A known unknown is closed only when Core can explain the answer without rereading the implementation line-by-line.
