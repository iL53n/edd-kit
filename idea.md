# EDD Kit: a measurement loop for agent-written LLM features

EDD Kit starts with a practical observation: code that runs is not necessarily behavior that works
well. Coding agents can implement a plausible feature quickly, while important quality gaps remain
invisible without representative scenarios and repeatable measurements.

The product adds one habit to the development loop:

> Describe the intended behavior briefly, measure it, change it, and measure it again.

## Product thesis

The primary users are developers building LLM-powered features with coding agents. The agent is the
authoring interface because it already has repository and product context. A local CLI supplies the
stable execution layer, run history, comparable deltas, and reports.

The approach borrows from specification-driven and test-driven development without requiring a
complete specification or a red test before implementation. Specifications can be wrong, verbose,
and stale. Evaluations can be shallow, overfit, and confidently wrong. EDD treats both as revisable
artifacts whose uncertainty must stay visible.

## The minimal contract

Each change needs:

- a short statement of intended behavior and important risks;
- stable requirements;
- executable scenarios with input and expected behavior;
- provenance for the scenario and its expectation;
- metrics and a runnable target;
- recorded measurements.

The scenario set is living. The team begins with a small, diverse sample and adds focused cases when
real development exposes a new failure class. Synthetic generation helps discover boundaries but
does not manufacture domain truth. Unresolved expectations are deferred rather than guessed.

## Evidence semantics

Execution health and behavior quality are separate decisions. A completed run can validly report a
behavior failure. Missing outputs, broken graders, and unavailable providers are execution gaps.

Numeric comparisons require the same scenario bundle and execution profile. When the golden set
changes, EDD shows what changed and preserves old runs, but it does not pretend that scores from
different instruments form a reliable trend. Rerun both application versions with the current
bundle when a direct delta matters.

The default report is diagnostic. It answers:

- What target and scenario set did we measure?
- Which behaviors passed or failed?
- Which cases are deferred?
- What evidence is missing?
- Is the comparison valid?

## Human role

The tool cannot guarantee that a specification is correct or that a golden set represents the
domain. It makes assumptions, provenance, changes, and gaps easy to inspect. Humans make
consequential product decisions and review high-risk expectations. The coding agent handles routine
scenario proposals, adapters, measurement runs, and bounded iteration.

## Progressive rigor

Ordinary development should remain lightweight: prepare, measure, build, compare, learn.

High-risk or governed work can add strict acceptance: positive and negative grader controls,
separate domain and technical decisions, full acceptance profiles, and a CI gate. This is an
optional branch, not a prerequisite for learning from the first measurement.

## Initial scope

The first product supports LLM features, DeepEval metrics, single-turn cases, and tool/state evidence
through adapters. It is local and repository-owned. Agent skills drive the workflow; CLI commands
run and preserve evidence; Markdown and JSON reports make it reviewable. A web approval interface
can follow only after real usage shows that chat, pull requests, and reports are insufficient.

Success is measured by whether teams find important behavior gaps earlier and can explain progress
with evidence, not by whether every project reaches a perfect specification or universal score.

See [workflow](docs/workflow.md), [authoring](docs/authoring.md), the
[landscape research](docs/research-sdd-landscape-2026-09.md), and the
[vision critique](docs/vision-review-2026-09.md).
