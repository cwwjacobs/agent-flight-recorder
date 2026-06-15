# AFR Runbook

Status: comprehension anchor
Audience: Core / future coding agents

## Purpose

This runbook is the first path for making AFR understandable and operable.

It is not a full release guide. It is the minimum path to prove the system runs.

## Docker path

From the repository root:

```bash
docker compose up --build
```

Then seed the demo:

```bash
make demo-docker
```

Open:

```text
http://localhost:8700
```

Expected result:

- backend and UI are running
- a demo run exists
- timeline is visible
- checkpoint can be selected
- replay plan can be prepared

## Non-Docker path

From the repository root:

```bash
make install
make serve
```

In another shell:

```bash
make build-ui
make demo
make demo-langchain
afr doctor
```

Open:

```text
http://127.0.0.1:8700
```

Expected result:

- runs dashboard loads
- demo run appears
- events are visible
- checkpoint/state/replay controls can be inspected

## First proof path

Run this sequence and capture output:

```bash
pwd
find . -maxdepth 3 -type f | sort | sed 's#^./##'
make install
make serve
# new shell
make build-ui
make demo
afr doctor
afr runs list
```

Then open the UI and confirm:

- run list visible
- run detail visible
- timeline visible
- event payload expandable
- checkpoint visible
- state inspector visible
- replay plan visible

## Learning path

For each command, Core should write one sentence:

```text
I ran <command>. It proves <thing>. It failed/passed because <reason>.
```

This converts terminal output into comprehension instead of noise.

## Failure recording rule

Failures are not shame. Failures are map updates.

Record each failure like this:

```text
Failure:
Command:
Observed result:
Expected result:
Likely component:
Return point:
Next map fix:
```

## Return rule

If a run command fails and Core cannot explain why, return to:

1. `SYSTEM_SUMMARY.md`
2. `PARTS_INDEX.md`
3. `DATA_FLOW.md`
4. this runbook

Then remap before changing code.
