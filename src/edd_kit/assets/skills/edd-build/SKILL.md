---
name: edd-build
description: Implement an LLM feature through short code-and-measure loops using a living EDD scenario set.
---

# Build through measurement loops

Use the prepared bundle as observable guidance. The cases and expectations may improve as the team learns; preserve their history and explain meaningful changes.

## 1. Establish the current measurement

Read the repository instructions, brief, contract, suite, target code, and `edd status CHANGE`. If no runnable bundle exists, use [edd-prepare](../edd-prepare/SKILL.md).

Measure the current application before changing it when possible:

```bash
edd measure CHANGE --target TARGET --stage baseline --profile dev
```

Record the returned run ID. A behavior `FAIL` provides a useful starting point when execution is complete.

## 2. Implement and compare a small slice

Choose one behavior or failure class, implement the smallest useful change, and run the repository's ordinary tests. Then measure the candidate against the saved baseline:

```bash
edd measure CHANGE --target TARGET --stage candidate --profile dev --compare-to BASELINE_RUN_ID
```

Read the case-level observations and execution gaps. Use the numeric delta only when EDD reports the runs as comparable. A changed scenario set, metric, profile, fixture, or policy requires a fresh measurement of both versions for a numeric comparison.

## 3. Learn from gaps

When a result exposes a distinct failure class, add a small group of focused cases, usually no more than five at once. Record why they were added and where their expectations came from. Prefer observed production or user examples; use synthetic cases to cover boundaries and rare risks.

Show the case-set diff. If the bundle changed, keep the older runs as history and rerun both relevant application versions before claiming improvement. Deferred cases remain visible and receive no pass/fail decision until their expectation is resolved.

Change metrics or expectations only when evidence shows that the measurement is wrong or the product intent changed. Do not lower a threshold merely to obtain a pass.

Stop and summarize after three iterations without meaningful movement. Identify whether the blocker is application behavior, evaluation quality, missing evidence, or an unresolved product decision.

## 4. Finish at the required confidence level

For normal development, finish with a fresh measurement report, comparable delta when available, ordinary test results, and remaining gaps. A completed measurement can report behavior `FAIL`; that means the instrument ran and found a problem.

When the user explicitly requires a formal gate, continue with [edd-check](../edd-check/SKILL.md) and its strict acceptance branch.
