# Implementation contract

This document supersedes the audit-first/Promptfoo-first proposal in `docs/idea-audit-first.md`. The original
research remains historical context. The user selected a local open-source Python CLI and CI kit,
DeepEval, coding-agent authoring, single-turn LLM features with tool/state evidence, and cooperative
reviewed code. There is no hosted service, autonomous coding agent, or hostile-code sandbox.

## Required deliverables

1. Package and documented `edd` CLI; reproducible DeepEval 4.2.3 evaluator dependencies.
2. Safe initialization, targeted coding-agent skills, change scaffolding, brownfield discovery,
   specialist-readable review packets, separate domain and technical decisions, persistent
   status/resume, customization-preserving integration sync,
   and one shared guided workflow view for human and JSON consumers.
3. Native Python `build_suite()` entrypoint with cases, traceable control provenance, fresh metric
   factories, requirements and explicit dev/acceptance execution policies. Human review remains a
   separate versioned decision. No generic metric expression DSL.
4. Working grader audit, actual target execution, honest baseline classification, acceptance gates,
   criteria/target/environment fingerprints, durable per-observation JSON and consolidated
   Markdown/JSON reports with fresh-versus-saved provenance.
5. Independent target process environment, bounded time/output/work, cancellation cleanup, explicit
   evaluator credential references, no implicit dotenv/telemetry/cloud upload, and no raw secrets.
6. Separate PASS, FAIL, ERROR, INCONCLUSIVE; missing, duplicate, malformed or stale evidence cannot
   pass. Critical violations cannot be averaged away. Expected red baseline is not broken setup.
7. Offline cancellation demo with good and deliberately defective targets, fixture evidence,
   a repository-isolated `edd demo cancellation` entry point, starter scaffold for new domains,
   and at least one independently authored non-demo feature.
8. Agent workflow validation, CLI end-to-end tests, fault/integrity tests, packaging smoke test,
   CI templates, supported-runtime CI, security/trust documentation and release instructions.

## Public test seams

The user-approved CLI/CI interface, Python suite entrypoint/native DeepEval grading adapter,
target JSON process protocol, and scaffold functions are the seams under test. Develop vertical
slices with a failing behavioral test before each implementation; avoid private-helper tests.

Human status output leads with phase, progress, responsible actor, and one next action. The JSON
form retains evidence decisions while adding the same workflow, structured diagnostics, and ordered
actions. Review preview is read-only; digest-guarded domain/technical decisions and target inference
fail before mutation or execution when the request is stale or ambiguous.

## Workflow and ownership

Prepare discovers relevant context, clarifies consequential decisions, writes the behavior brief,
authors and validates the pipeline, supports explicit review, and runs the available baseline. Build starts
from current readiness and iterates implementation against dev evaluations. Check runs fresh full
acceptance and verifies evidence. Release remains in the adopting project's deployment workflow.

`evals/<change>/` contains durable user-owned criteria, generated `REVIEW.md`, and the portable,
digest-versioned `review.json` history.
`targets/<change>/` contains independently changing target code. `.edd/` contains local run/review
history and progress notes, not external authenticated approval.
Kit templates/skills are managed separately. A same-PR review does not prove historical chronology.

Evaluation fingerprints include all evaluation files and declared external artifacts plus runtime
dependencies. Target fingerprints include declared source files, resolved command and environment
identity without exposing values. Mutable remote resources require explicit version references;
fingerprints cannot prove remote reproducibility or prevent malicious report fabrication.

## Completion evidence

The [verification record](verification.md) maps every numbered deliverable to inspected source and
actual execution results, including installed distributions, independent generated workflows and
adversarial failures. It distinguishes local verification from hosted CI, live providers and
publication. Green unit tests alone do not prove this contract; recheck that evidence after changes.
