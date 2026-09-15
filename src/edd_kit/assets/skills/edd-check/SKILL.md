---
name: edd-check
description: Run fresh acceptance evaluations for a prepared EDD change and explain its control audit, candidate decision, baseline comparison, and evidence gaps.
---

# Check the current candidate

Produce fresh acceptance evidence for the selected change. A check request authorizes evaluation and local reports; it does not by itself request implementation changes or publication.

## 1. Inspect the current inputs

Read the selected change's contract and run `edd status CHANGE --json` and
`edd inspect CHANGE --json`. Resolve an ambiguous change name before execution. Use the shared
workflow state and diagnostics to identify the candidate target, acceptance profile, required
evidence, current review, baseline provenance, and first blocking action.

Read [the authoring reference](../edd-prepare/references/authoring.md) when interpreting adapters, fixture evidence, native metrics, or comparison rules. Use the installed CLI's `--help` for the supported command options.

A changed contract, grader, control, fixture, or policy can invalidate prior evidence. Retain stale results as history; use the current evaluation version for this decision. If review is missing, explain that acceptance remains unavailable even if diagnostic evaluation can run. Only record a review when the user has explicitly made that decision for the current contents.

## 2. Execute and verify

Run the configured controls, a fresh candidate evaluation, verification, and one consolidated
report:

```bash
edd check CHANGE --target TARGET --report-dir .edd/CHANGE/report --revision REVISION
```

Use the configured budgets and provider settings. If execution is blocked, retain its actual error or incomplete outcome and complete the independent checks that remain possible. Treat cached or replayed results according to their recorded identity; they are not fresh independent application trials.

Inspect `report.md` and the individual recorded evidence, not only a native DeepEval summary or a
command's green output. The report labels runs created by this check as fresh and prior records as
saved. The deterministic verifier is the authority for the declared gate. A known bad control
rejected by its intended grader is a successful audit observation, even though that underlying
application-level observation fails.

## 3. Explain the decision

Report these separately:

- **Control audit:** whether the current graders distinguish the reviewed good and bad outcomes, including false passes and false failures.
- **Candidate acceptance:** the verifier's decision for the actual candidate and acceptance profile, with critical violations and incomplete execution visible.
- **Baseline comparison:** changes under comparable criteria, or the explicit reason no comparison is supported. Baseline failure does not itself fail the candidate; improvement does not itself establish acceptance.
- **Scope and evidence:** target identity, replay/stub/live distinction, authoritative state collection where required, scenario/trial counts, and links to reports.

For every non-passing outcome, identify the unmet requirement or execution problem and its next action. Request necessary domain clarification without silently editing the criteria to match observed output.

Completion: fresh execution and verification have produced inspectable evidence, or the exact blocked/incomplete state has been recorded. For a check-only request, hand back the findings. If the user already asked to fix and finish the feature, return to [edd-build](../edd-build/SKILL.md) for the affected implementation work. Acceptance does not authorize merge, deployment, or publication.
