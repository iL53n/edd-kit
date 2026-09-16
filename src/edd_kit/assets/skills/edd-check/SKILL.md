---
name: edd-check
description: Measure an LLM feature, compare compatible runs, and explain behavior failures separately from execution problems.
---

# Check the current behavior

Produce inspectable evidence for the selected change. Use the installed CLI's `--help` for exact syntax.

## 1. Inspect the bundle

Read the brief, contract, cases, relevant target code, and `edd status CHANGE`. Use [the authoring reference](../edd-prepare/references/authoring.md) when interpreting metrics, adapters, fixtures, or provenance.

Confirm the intended target and profile. Note deferred cases and unresolved assumptions before running the measurement.

## 2. Measure and compare

Run a fresh candidate measurement:

```bash
edd measure CHANGE --target TARGET --stage candidate --profile dev --compare-to BASELINE_RUN_ID
```

Omit `--compare-to` when no relevant baseline exists. You can compare saved runs separately with:

```bash
edd compare CHANGE --before RUN_ID --after RUN_ID
```

Inspect `report.md`, not only the terminal summary. Report two decisions separately:

- **Execution status:** whether the measurement completed, is inconclusive, or hit an execution error.
- **Behavior decision:** what the configured requirements and metrics observed, including `PASS`, `FAIL`, or `INCOMPLETE`.

Treat a behavior failure as a valid measurement result. Do not claim a numeric improvement when EDD marks the comparison unavailable. Explain added, removed, and changed cases and suggest rerunning both application versions with the current bundle.

## 3. Hand back useful evidence

Summarize the target identity, scenario and observation counts, important failures, deferred cases, comparison status, cost, and remaining evidence gaps. Link the generated Markdown and JSON reports.

If the user asked to fix the behavior, return to [edd-build](../edd-build/SKILL.md) and repeat the loop. When the user explicitly requires a release gate, reviewer sign-off, or compliance evidence, follow [the strict acceptance workflow](../edd-prepare/references/acceptance.md).
