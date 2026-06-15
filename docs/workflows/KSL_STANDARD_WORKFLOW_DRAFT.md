# KSL Standard Workflow — Draft for Core Review

Status: draft
Owner: Core
Mode: Work Mode

KSL means:

```text
Kernel -> Spine -> Loop
```

It is a three-stage workflow for turning an intention into a mapped build, then crushing the result against the original Kernel before deciding whether to exit, repair, or begin a new version.

---

# KSL MAP

```text
* Stage 1: Iterative Kernel Surfacing and Locking
|   L-- surface Kernel
|   L-- define Goal
|   L-- define Scope
|   L-- map Phase Spine
|   L-- lock completion check
|
* Stage 2: Build Stage / Walk the Spine
|   L-- Phase: overarching phase goal
|       L-- Step: action space inside the phase
|   L-- if blocker appears -> Stage 1
|   L-- if map breaks -> Stage 1
|   L-- if map holds -> continue
|
* Stage 3: Architecture Crush and Repair
    L-- crush-check what was created
    L-- if it crumbles -> Stage 1
    L-- if it holds -> repair/bolster cracks
    L-- compare result to Kernel and Goal
    L-- if aligned and complete -> exit loop
    L-- if misaligned or incomplete -> Stage 1
    L-- future changes start a new KSL loop
```

---

# Stage 1 — Iterative Kernel Surfacing and Locking

## Purpose

Stage 1 finds the smallest true Kernel, defines the Goal, defines the Scope, and lays out the Phase Spine before any build work begins.

## Kernel

The Kernel is the most reduced single-scope statement of outcome intent.

It should be short enough to hold in one breath.

Examples:

```text
Does X.
Exposes Y.
Produces Z.
Records agent runs.
Shows replay state.
Exports proof.
```

The Kernel is not the full plan.
The Kernel is not the feature list.
The Kernel is not the emotional explanation.

The Kernel is the irreducible outcome-intent statement.

## Goal

The Goal is the more detailed intent statement.

It explains the Kernel enough to guide the work:

```text
Kernel: Exports proof.
Goal: Export a recorded AFR run into a readable evidence bundle containing run metadata, ordered events, checkpoints, errors, replay context, and known limitations.
```

## Scope

Scope defines what is inside and outside the current loop.

```text
In scope: what this loop is allowed to touch.
Out of scope: what this loop must not expand into.
```

## Phase Spine

Stage 1 lays out the Stage 2 traversal map.

Only three structural levels are required:

```text
Stage
  L-- Phase
      L-- Step
```

A Phase is an overarching phase goal that brings the work closer to completion.
A Step is the action space inside that Phase.

No deeper formal scope is required by default. Extra detail can live inside the Step text when needed, but it does not become a new KSL level.

## Stage 1 lock condition

Stage 1 is locked only when Core can say:

```text
This is the Kernel.
This is the Goal.
This is the Scope.
This is the Phase Spine.
This is how we know when to return and remap.
```

---

# Stage 2 — Build Stage / Walk the Spine

## Purpose

Stage 2 walks the mapped Phase Spine.

It builds, changes, repairs, packages, tests, or documents according to the map created in Stage 1.

## Stage 2 structure

```text
* Stage 2: Build Stage / Walk the Spine
|   L-- Phase 1: overarching phase goal
|       L-- Step 1: action space
|       L-- Step 2: action space
|
|   L-- Phase 2: overarching phase goal
|       L-- Step 1: action space
|       L-- Step 2: action space
```

A Phase may have one Step.
A Phase may have many Steps.
The size depends on the work.

## Stage 2 rule

Walk the spine in order unless the map becomes wrong.

For each Phase:

```text
1. restate the Phase goal
2. walk the Steps
3. record output/evidence
4. check for blocker, drift, or map failure
5. continue only if the map still holds
```

## Blocker return

If a blocker surfaces:

```text
Stop.
Return to Stage 1.
Remap or fix the map.
Reenter Stage 2 where necessary.
```

## Drift return

If the work starts solving a different problem than the Kernel:

```text
Stop.
Return to Stage 1.
Compare the work against the Kernel and Goal.
Either restore the original map or intentionally define a new Kernel.
```

## Map failure return

If the Phase Spine was wrong or incomplete:

```text
Stop.
Return to Stage 1.
Repair the Phase Spine.
Reenter the correct Stage 2 point only after the map is repaired.
```

---

# Stage 3 — Architecture Crush and Repair

## Purpose

Stage 3 crush-checks what was created.

It tests whether the work holds against:

```text
Kernel
Goal
Scope
architecture
operator usability
evidence/proof
known limitations
```

Stage 3 decides whether the loop exits, repairs, or returns to Stage 1.

## Crush check

Ask:

```text
Does the created thing actually satisfy the Kernel?
Does it satisfy the Goal?
Did the Scope drift?
Does the architecture hold?
What crumbles under use?
What cracks but still holds?
What is confusing?
What is unsupported?
What needs proof?
What needs repair?
```

## If it crumbles

```text
Return to Stage 1.
Map the repair.
Walk the repair through Stage 2.
Return to Stage 3.
```

## If it holds but has cracks

Repair or bolster the cracks:

```text
patch confusing paths
document weak points
add missing proof
tighten language
record limitations
simplify where possible
```

Then check again.

## Alignment check

Compare created output to the Kernel and Goal:

```text
Kernel: did the work produce the reduced outcome intent?
Goal: did the work satisfy the detailed intent statement?
Scope: did the work stay inside the loop boundary?
```

## Exit condition

If the Kernel and Goal are good, and Stage 3 holds:

```text
Exit the loop.
Record/version the result.
Do not keep working inside the same loop.
```

## Future-change rule

Any future change must be designed in KSL format.

That means a future change does not casually reopen the old loop. It starts a new KSL pass:

```text
new Kernel or same Kernel with new Goal
new Scope
new Phase Spine
Stage 2 walk
Stage 3 crush and repair
exit if aligned
```

---

# Standard failure terms

```text
BLOCKER: work cannot continue with the current map.
DRIFT: output no longer matches Kernel or Goal.
MAP FAILURE: Phase Spine is wrong, missing, or misleading.
CRACK: architecture holds but has weak points.
CRUMBLE: architecture fails the crush check.
REPAIR WALK: a mapped repair pass through Stage 1 -> Stage 2 -> Stage 3.
LOOP EXIT: Kernel and Goal are satisfied; result is recorded/versioned.
NEW KSL PASS: future work starts from Stage 1 again.
```

---

# Compact form

```text
* Stage 1: Iterative Kernel Surfacing and Locking
|   L-- Kernel: most reduced single-scope outcome intent
|   L-- Goal: detailed intent statement
|   L-- Scope: current loop boundary
|   L-- Phase Spine: Stage -> Phase -> Step
|
* Stage 2: Build Stage / Walk the Spine
|   L-- Phase: overarching phase goal
|       L-- Step: action space
|   L-- blocker/drift/map failure returns to Stage 1
|
* Stage 3: Architecture Crush and Repair
    L-- crush-check result against Kernel, Goal, Scope
    L-- if crumble -> Stage 1
    L-- if crack -> repair/bolster/check again
    L-- if aligned -> exit loop and version
    L-- future changes require new KSL pass
```

---

# Core review points still open

1. Confirm exact Stage 3 name: `Architecture Crush and Repair`.
2. Confirm whether `Kernel` should always be written in verb form: `Does X`, `Exposes Y`, `Produces Z`.
3. Confirm whether `Phase` and `Step` are enough for all public docs, with extra detail kept informal inside Step text.

Current draft status: revised from Core's June 15, 2026 edits. Not final until Core accepts it.
