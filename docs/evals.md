# AFR evals

AFR eval records describe observable agent-run failure shapes that should become repeatable tests. They are not training data, model outputs, or claims about hidden reasoning. They are small public fixtures for checking whether AFR preserves the right boundary evidence.

## Eval spine

1. Record the failure with AFR.
2. Inspect the run timeline and checkpoint state.
3. Export the run bundle.
4. Generate a regression case from the checkpoint.
5. Add or update an eval record only when the failure shape is stable and reusable.

## Public seed schema

Each line in `evals/afr_sanity_eval.jsonl` uses this shape:

```json
{
  "id": "afr-sanity-001",
  "split": "eval",
  "task": "Describe the behavior the system must support.",
  "given": {
    "run_status": "failed",
    "events": ["model_call", "tool_call", "error"],
    "checkpoint": "before-retry"
  },
  "must_preserve": ["observable evidence expected in the recording"],
  "must_not_claim": ["unsupported claim AFR must avoid"],
  "pass_conditions": ["checkable expected result"],
  "failure_modes": ["known unacceptable result"],
  "metadata": {
    "source": "repo-authored public seed",
    "contains_user_data": false
  }
}
```

## Rules

- Keep eval records source-bound and checkable.
- Do not include private prompts, secrets, raw production traces, or unredacted payloads.
- Do not claim AFR captured hidden reasoning or model intent.
- Prefer one crisp failure shape per record.
- Promote only stable recurring failures into evals; one-off noise belongs in local regression cases.
