# Agent Review Gate

Use this checklist after an AI coding agent proposes changes in Agent Flight Recorder.

## Task

- Requested change:
- Scope:
- Expected output:

## Diff Review

- [ ] Diff is scoped to the task.
- [ ] No unrelated files changed.
- [ ] No tests were removed or weakened to force a pass.
- [ ] No dependency was added without justification.
- [ ] No replay, redaction, storage, API, or CLI boundary changed unexpectedly.
- [ ] Documentation claims still match implemented behavior.
- [ ] Sensitive-data warnings remain accurate.

## Verification

- [ ] `make test` run for backend-affecting changes, or reason recorded.
- [ ] `make build-ui` run for UI-affecting changes, or reason recorded.
- [ ] `make smoke` considered for end-to-end behavior, or reason recorded.
- [ ] Failures are explained rather than hidden.

## Result

Decision:

```text
accept / request repair / reject / hold
```

Notes:

```text

```
