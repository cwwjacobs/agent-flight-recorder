# KSL Standard Workflow — Draft for Core Review

Status: draft
Owner: Core
Mode: Work Mode

## One-line definition

KSL is a three-stage recursive workflow:

```text
Stage 1 maps and locks the Kernel.
Stage 2 walks the phased Step Spine.
Stage 3 breaks, checks, bolsters, versions, and returns to Stage 1.
```

## Core rule

Every blocker, drift, failed check, broken architecture point, or required fix returns to Stage 1.

Returning to Stage 1 is not failure. It is how the map stays true.

---

# Stage 1 — Iterative Kernel Surfacing and Locking

## Purpose

Surface and lock the Kernel before building.

The Kernel is the smallest true statement of the work:

```text
What are we doing?
Why are we doing it?
What must be true when it is done?
```

## Stage 1 outputs

Stage 1 produces:

1. Kernel statement
2. scope boundary
3. goal definition
4. constraints
5. current known unknowns
6. Phased Step Spine Traversal map
7. return conditions
8. completion criteria

## Stage 1 questions

```text
What is the actual objective?
What is in scope?
What is out of scope?
What does done mean?
What would count as drift?
What would count as failure?
What are the phases?
What are the steps inside each phase?
What must be checked before building?
```

## Stage 1 lock condition

Stage 1 is locked only when Core can say:

```text
This is the Kernel.
This is the scope.
This is the goal.
This is the spine we will walk.
This is how we know when to return and remap.
```

---

# Stage 2 — Build Stage: Walk the Spine

## Purpose

Execute the Phased Step Spine Traversal map.

Stage 2 is where work is built, changed, repaired, packaged, or tested.

## Phase structure

A phase is an overarching goal that brings the work closer to completion.

```text
Phase: overarching phase goal
  Step: one required movement inside the phase
    Substep: optional smaller movement
      Detail: optional deeper action when needed
```

A phase may contain one step.
A phase may contain many steps.
The size depends on the thing.

## Stage 2 execution rule

Walk the mapped phases in order unless the map becomes wrong.

For each phase:

1. restate the phase goal
2. walk the steps
3. record evidence/output
4. check for blocker/drift/failure
5. continue only if the map still holds

## Stage 2 blocker rule

If a blocker surfaces:

```text
Stop.
Return to Stage 1.
Remap or fix the map.
Reenter Stage 2 where necessary.
```

Do not brute-force through a broken map.

## Stage 2 drift rule

If the work starts solving a different problem than the Kernel:

```text
Stop.
Return to Stage 1.
Compare current work against the Kernel.
Decide whether to restore the original map or intentionally define a new Kernel.
```

---

# Stage 3 — Architecture Break, Alignment Check, Bolster, Version

## Purpose

Break-check what was created, compare it against the Kernel, repair cracks, and decide whether the work can complete or must reenter Stage 1.

Stage 3 is not decoration. It is where weak work gets exposed before it ships.

## Stage 3 checks

### 1. Architecture break

Ask:

```text
Does this crumble under inspection?
What assumptions fail?
What dependency breaks?
What path is confusing?
What output is unsupported?
What user path is ugly or unusable?
```

### 2. If it crumbles

```text
Return to Stage 1.
Map the fix.
Walk the fix through Stage 2.
Return to Stage 3.
```

### 3. If it holds

Bolster the cracks:

```text
document weak points
patch confusing paths
add missing proof
tighten language
record limitations
version the result
```

### 4. Kernel alignment check

Compare what was created against the Kernel:

```text
Did we build the thing we said we were building?
Did the goal drift?
Did scope creep enter?
Did the output satisfy the original completion criteria?
What claim is unsupported?
What needs evidence?
```

### 5. Completion or return

If aligned:

```text
Complete the version.
Record the version.
Return to Stage 1 for the next version or next Kernel.
```

If misaligned, failed, incomplete, or needing repair:

```text
Return to Stage 1.
Map the fix walk.
Reenter Stage 2 only after the map is corrected.
```

---

# Standard KSL loop

```text
Stage 1: Iterative Kernel Surfacing and Locking
  L define Kernel
  L define scope
  L define goal
  L map Phased Step Spine
  L lock completion criteria

Stage 2: Build Stage / Walk the Spine
  L Phase: overarching phase goal
      L Step
          L Substep if needed
              L Detail if needed
  L if blocker/drift/failure surfaces -> Stage 1
  L if map holds -> continue spine

Stage 3: Architecture Break and Alignment Check
  L break-check architecture
  L if crumbles -> Stage 1
  L if holds -> bolster cracks
  L compare output to Kernel
  L if aligned -> complete/version
  L if not aligned or needs fix -> Stage 1
  L next version always reenters Stage 1
```

---

# Failure language

Use direct failure language:

```text
BLOCKER: map cannot continue.
DRIFT: output no longer matches Kernel.
CRACK: architecture holds but has weak points.
CRUMBLE: architecture fails inspection.
FIX WALK: a mapped repair pass through Stage 1 -> Stage 2 -> Stage 3.
VERSION RETURN: completed work reenters Stage 1 for the next version.
```

---

# Core review questions

Core should edit this draft by answering:

1. Is `Iterative Kernel Surfacing and Locking` the exact Stage 1 name?
2. Is `Build Stage: Walk the Spine` the exact Stage 2 name?
3. Is `Architecture Break` the exact Stage 3 name, or should it be `Architecture Break and Bolster`?
4. Should `Kernel` include emotional/mission intent, or only objective/scope/goal?
5. Should every version return to Stage 1 automatically, even for tiny patch releases?
6. What words should be forbidden because they flatten the system?

---

# Current draft status

This is the first standardized KSL workflow draft based on Core's June 15, 2026 instruction.

Do not treat this as final until Core reviews and edits it.
