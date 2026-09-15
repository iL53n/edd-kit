---
name: edd-build
description: Implement or resume an LLM feature from a prepared EDD evaluation pipeline, using its checked criteria and baseline to guide the development loop.
---

# Build against the prepared pipeline

Use the existing coding agent to implement the requested feature. EDD supplies acceptance evidence and readiness checks; it does not replace the coding agent or authorize deployment.

## 1. Recover readiness

Read the repository instructions and the selected change's contract, brief, evaluation code, and recorded progress. Run `edd status CHANGE --json` and `edd inspect CHANGE --json`. Select the change explicitly when more than one is plausible.

Use the reported `workflow`, `diagnostics`, and first blocking `action` rather than inferring
readiness from files existing or an old green summary. The implementation loop needs a
feature-specific pipeline, an accepted review for its current contents, a valid control audit, and
an honest baseline state. If preparation is missing or stale, use
[edd-prepare](../edd-prepare/SKILL.md) to complete only the reported blocking work before production
implementation.

When editing an adapter, grader, fixture, or execution policy, read [the authoring reference](../edd-prepare/references/authoring.md). Preserve the distinction between changing target code and the evaluation bundle.

Completion: the current artifacts and CLI state agree on what is being implemented, how it will be checked, and which baseline is available. Surface unmet prerequisites with the concrete corrective action.

## 2. Plan and implement one behavior at a time

Derive a small implementation plan from the prepared requirements and existing code. Link each behavior to its relevant cases and evidence collection. Keep progress in `.edd/CHANGE/progress.md` or the repository's existing task mechanism outside the fingerprinted evaluation artifacts. Updating task completion must not invalidate reviewed acceptance criteria. Another session resumes from these notes and current run records.

Implement the smallest useful slice, preserve existing application conventions, and run the appropriate ordinary software tests. Use the configured candidate target for development feedback:

```bash
edd run CHANGE --target TARGET --stage candidate --profile dev
```

Inspect per-requirement evidence and execution health. Distinguish an application failure from an unavailable provider, malformed metric result, or broken fixture. A development pass supports iteration; the acceptance profile determines final acceptance.

Completion for a slice: its relevant cases exercise the implementation and the observed outcomes satisfy the declared development policy, with execution gaps still visible.

## 3. Handle discoveries explicitly

When implementation reveals an unclear requirement or demonstrably incorrect grader, return to the affected preparation step. Explain the proposed criterion change and its reason, preserve the original failure evidence, and refresh the affected controls, review, audit, and baseline comparison under the changed evaluation bundle.

Keep the intended acceptance behavior fixed while fixing implementation failures. Threshold reductions, relabelled goldens, and skipped cases are criterion changes, not ordinary ways to make the implementation pass. Apply only changes justified by the user's requirement or an explicit revision decision.

On resume, reread files and current status, check what actually changed, and continue from the first unfinished prerequisite or behavior. Preserve custom edits and previous runs. Avoid repeating paid evaluations whose current evidence already answers the development question.

## 4. Complete with acceptance evidence

Once the implementation is ready, use [edd-check](../edd-check/SKILL.md) for a fresh acceptance run and verification. Continue fixing in-scope application failures and rerun the checks affected by each change. Stop when acceptance is established, or when an unresolved product decision, required access, or configured execution limit prevents progress.

Report the implemented behavior, candidate acceptance, baseline comparison when supported, ordinary
test results, and remaining limitations with artifact links. End with the phase and exactly one
next action from current status. A satisfactory result may require no application change if the
current target already meets the contract. Keep merging, publishing, and deployment subject to the
user's separate task scope.
