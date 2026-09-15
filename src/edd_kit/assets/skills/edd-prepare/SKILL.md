---
name: edd-prepare
description: Generate or revise an executable EDD evaluation pipeline before implementing an LLM feature, in a new or existing application.
---

# Prepare the evaluation pipeline

Turn the requested behavior into executable acceptance criteria before writing its production implementation. The `edd prepare` terminal command creates a scaffold; you author the feature-specific pipeline using the existing coding agent.

## 1. Recover the change and its intent

Read [the authoring reference](references/authoring.md) before creating or editing evaluation code. Use the installed CLI's `--help` for command syntax.

Read the repository instructions, the user's brief, relevant product specifications, and the code and tests around the proposed change. For an existing application, identify the current target interface and reusable fixtures and metrics. For a new application, establish the smallest target interface and test-only stub needed to run evaluations. Scope this work to the requested behavior; an existing eval suite is optional.

Run `edd status --json` when the project is initialized. If the change exists, inspect its files and
`edd status CHANGE --json`; use its `workflow`, `diagnostics`, and ordered `actions` to continue from
the first blocking action rather than regenerating artifacts or reciting the full lifecycle. Resolve
an ambiguous change name before editing.

Completion: identify the behavior, inputs, acceptable outputs or state changes, critical constraints, and available evidence sources. Separate facts from proposed assumptions. Ask for product decisions that materially change correctness; finish independent preparation while those decisions remain unresolved.

## 2. Author the pipeline

For a new change, use `edd prepare CHANGE --brief TEXT --template starter`. The cancellation template is a synthetic teaching example; use it only when requested or relevant. Preserve custom files and manual edits when revising an existing change.

Replace scaffold behavior with the requested domain's executable pipeline:

- A contract with stable requirement IDs, scope, applicable cases, per-requirement acceptance policy, execution profiles, and evidence requirements.
- Native DeepEval cases and reference outcomes, plus specialist-readable descriptions of expected,
  acceptable, and unacceptable behavior.
- Fresh native metric factories mapped to those requirements. Use deterministic checks for schemas, authorization, state changes, and other objective outcomes; reserve model judgment for criteria that require it.
- Positive and negative controls for each grader. Record the related case, rationale, contributor,
  source, and whether a negative control was authored independently of the grader.
- Fixtures, target adapters, and evidence collection sufficient to run the pipeline. Collect state and action history from fixture-owned or service-owned observations when the behavior changes external state.
- A bounded development profile and the declared acceptance profile, with the configuration needed for repeatable local and CI execution.

Keep changing application targets separate from evaluation files as described in the authoring reference. A test-only stub is allowed before production implementation and must remain identified as a stub.

For every reference outcome and control label, record its actual source. Agent-generated labels
remain proposals until reviewed. Contributor and independence fields are declared provenance, not
authenticated identity. Keep examples used to tune a grader in calibration data; reserve separately
selected examples for validation.

Completion: the requirement-to-case-to-grader mapping describes this feature, and the pipeline can be executed through EDD. Leave unresolved domain assumptions visible instead of substituting a generic metric or fabricated golden answer.

## 3. Validate the checks

Run `edd inspect CHANGE --json`, resolve configuration and case-mapping errors, then run `edd audit CHANGE` against the authored controls. Inspect individual observations as well as the command result.

For each mismatch, determine whether the expected label, grading logic, or collected evidence is wrong. Repair demonstrated evaluator defects and rerun good and bad controls. A stricter grader is useful only if legitimate outcomes remain accepted. A crash or an unexercised fault does not demonstrate sensitivity to the intended defect.

Use the configured provider settings and execution limits. If credentials, evidence access, or an essential domain decision are missing, complete the runnable offline work and name the remaining limitation precisely.

Completion: configuration is valid, the actual native graders have been exercised, and the report states which reviewed distinctions they handle. A passing synthetic or replay audit establishes only its declared scope.

## 4. Record the preimplementation baseline

Use a configured target shown by `edd inspect`, then run:

```bash
edd run CHANGE --target TARGET --stage baseline --profile acceptance
```

For an existing application, prefer its current behavior. For greenfield work, use the explicit test-only stub or reference and retain that identity in the evidence. If a meaningful baseline cannot execute, use `edd baseline-unavailable CHANGE --reason TEXT` to record the limitation; an import error is an execution error, not proof of missing capability.

Use the acceptance profile when a direct comparison with the final candidate is intended. A cheaper development baseline can guide implementation, but it cannot substitute for matching acceptance-profile baseline evidence. Missing comparable baseline evidence leaves comparison unavailable; it does not by itself prevent standalone candidate acceptance.

Some baseline cases may already pass, especially prohibitions. If the current application already satisfies the requested behavior, report that result instead of manufacturing a red baseline.

Completion: the baseline is genuinely executed and identified, or its unavailability is explicit. Production feature implementation has not started during preparation.

## 5. Review and hand off

Run `edd review CHANGE --write`, then show the user the committed `REVIEW.md`; they should not need
Python or JSON. Record domain `approve`, `request_changes`, or `needs_discussion` with the displayed
digest, actual reviewer name, rationale, and optional `requirement:ID` or `case:ID` subject. Feedback
does not edit criteria. Make requested canonical changes explicitly, regenerate the packet, and show
its semantic diff before approval of the new digest.

After domain approval, run `edd audit CHANGE`. Record technical approval only after an engineer has
reviewed the grader section and the current audit passes. Technical feedback may reference
`requirement:ID` or `control:ID`. A passing audit demonstrates the declared known examples only.
Refresh the acceptance-profile baseline after criteria changes, or refresh its explicit unavailable
reason. Both review areas remain blockers until approved.

Run `edd status CHANGE --json` and follow its first blocking `action`. End a preparation-only request
with the current phase, the decision-relevant evidence, links to the pipeline, and exactly one next
action. For an already authorized full-feature task, continue with
[edd-build](../edd-build/SKILL.md) once its prerequisites are satisfied.

## Revising or resuming

Read the current artifacts first. Refine the same change when its intent remains the same; use a new change when the objective materially changes. Update affected requirements, controls, metrics, and fixtures together, preserving unrelated work. Criteria changes require fresh audit/review evidence and comparable baseline evidence; show stale runs as stale. Retain previous runs for explanation rather than rewriting their outcomes.
