# Generate the checks before building the feature

EDD uses your coding agent to author an executable evaluation pipeline, then uses a local CLI and DeepEval to run it. The pipeline covers the requested behavior in a new or existing application. You can start without an existing evaluation suite.

## Terminal setup, then agent skills

Initialize the repository in your terminal:

```bash
edd init --agent codex
```

Use `--agent claude` for Claude Code or `--agent none` to use the CLI without installed skills. Initialization prints the installed files and the appropriate invocation for your agent. It does not generate your feature's acceptance criteria.

In Codex chat, use:

```text
$edd-prepare Add an assistant that cancels an eligible order owned by the user.
$edd-build <change>
$edd-check <change>
```

The preparation skill generates evaluation code and supporting fixtures before production feature code. The build skill implements against that pipeline. The check skill runs fresh acceptance evaluations and explains the evidence. A request to complete a feature can carry the whole workflow forward once required product decisions are resolved.

## What preparation produces

Bring the behavior you want, relevant product specifications, and any known edge cases. In an existing application, point the agent at the area being changed; you do not need to document the rest of the codebase.

The agent creates a change with:

- A contract identifying the required outcomes, constraints, acceptance policy, and evidence needed.
- Native DeepEval cases, metric factories, and reference outcomes suited to the behavior.
- Good and bad controls that check the graders themselves, including legitimate alternatives.
- Fixtures, adapters, and an executable baseline target or an explicit record that a meaningful baseline is unavailable.
- Development and acceptance execution profiles and the files needed for local and CI checks.

Goldens describe acceptable outcomes; they need not be exact answer strings. A stateful feature may need authoritative state and action history alongside the assistant's response. Generated labels have recorded sources and remain proposed until reviewed.

The terminal scaffold command is available directly:

```bash
edd prepare cancellation --brief "Cancel an eligible order owned by the user" --template starter
```

This creates starting files. The agent must adapt them to the feature and validate the resulting pipeline. The cancellation template is a separate synthetic demonstration, not evidence about your application's correctness.

## Read workflow status

`edd status` shows all changes grouped by Prepare, Build, Check, and Complete. For one change,
`edd status CHANGE` leads with its phase, progress, responsible actor, and one next action. Add
`--verbose` for the underlying evidence decision and diagnostics.

Agents and CI should use `--json`. The existing review, audit, baseline, candidate, decision, and
exit-code fields remain authoritative. The additive `workflow`, `diagnostics`, and `actions` fields
provide the same guidance as the human view; diagnostic codes are stable identifiers while message
text may improve between releases.

## Review the pipeline, then implement

Preparation validates configuration, produces the specialist packet, records domain approval, runs
the control audit, records technical validation, and captures a preimplementation baseline when
possible. A current application can provide a real baseline. A greenfield stub can demonstrate
missing capability while still passing constraints such as making no unauthorized changes. An
import crash is an execution problem, not a meaningful failing baseline.

`edd review CHANGE` prints deterministic Markdown with two explicit sections. The domain section
contains requirements, scenario inputs, expected behavior, alternatives, and unacceptable outcomes.
The technical section contains grader configuration, known controls, provenance, and the evidence
each control supplies. Write and commit it with `edd review CHANGE --write`.

Record `approve`, `request_changes`, or `needs_discussion` with `--area domain|technical`, the
packet's `--criteria-digest`, reviewer name, rationale, and an optional stable `--subject`. Domain
feedback can reference `requirement:ID` or `case:ID`; technical feedback can reference
`requirement:ID` or `control:ID`. The repository-visible `review.json` retains events by criteria
digest. Feedback never changes criteria or control labels. Edit canonical files explicitly,
regenerate the packet, and review its semantic revision diff.

Run `edd audit CHANGE` after domain approval. Technical approval requires that current audit to
pass. Both human decisions, the audit, and a current committed packet are required for readiness.
A passing audit proves only that the grader handled its declared controls; it is not universal
grader validation.

The current review, pipeline readiness, and evaluation results are separate facts. Use:

```bash
edd status cancellation
edd status cancellation --verbose
edd inspect cancellation --json
```

Once preparation is ready, the build skill reads those artifacts, derives an implementation plan, and runs the development profile as it changes the application. It uses ordinary software tests for the surrounding implementation as well as the LLM feature evaluations.

## Run and verify directly

Choose target names from the generated configuration or `edd inspect` output:

```bash
edd audit cancellation
edd run cancellation --target current --stage baseline --profile acceptance
edd run cancellation --target candidate --stage candidate --profile dev
edd run cancellation --target candidate --stage candidate --profile acceptance
edd verify cancellation
```

`current` and `candidate` above are illustrative configured target names. The check skill runs the control audit and fresh acceptance evaluation before verification; `edd verify` assesses recorded evidence rather than silently performing more model calls.
For `run` or `check`, `--target` may be omitted when exactly one target is eligible. Ambiguous
configurations stop before execution and print every valid explicit form.

Reports keep three conclusions separate: whether the control audit passed, whether the candidate met acceptance policy, and whether it improved over a comparable baseline. A candidate can improve while still failing acceptance. A deliberately weak baseline does not fail a satisfactory candidate.

A development-profile baseline can guide implementation, but direct acceptance comparison needs matching acceptance-profile baseline evidence. When a comparable baseline is unavailable, the report states that limitation while assessing candidate acceptance separately.

Provider-backed metrics require their configured credentials and execution budget. Missing access, exhausted budgets, and incomplete evidence remain visible in the result. A successful offline demonstration does not certify a live application.

## Revise and resume

Changes are files in the repository. Edit them yourself or ask the preparation skill to revise the same change. Refining an implementation approach can stay in the same change; a fundamentally different objective merits a new change.

When acceptance criteria change, review the reason and affected labels, rerun the controls, and refresh the baseline evidence needed for a direct comparison. Previous green results belong to their recorded evaluation version. The CLI identifies stale evidence; changing the criteria does not retroactively validate an old run.

To resume in another session, select the change and run its build or check skill. It reads current files, status, and evidence. Keep durable notes for decisions that would otherwise exist only in chat.

## Team review and CI

The same pull request can contain acceptance criteria, evaluation code, and implementation. Review the contract and label sources first, then the implementation and acceptance evidence. CI runs the configured pipeline and publishes its actual result.

The portable `review.json` records domain and technical events against criteria digests and retains
the snapshots needed for a semantic revision diff. Commit it with the generated `REVIEW.md` and
canonical criteria. Schema-v1 combined stamps remain visible as legacy but no longer satisfy the
two gates. `.edd/` retains local run and review history.

This workflow supports cooperative contributors. Local review records and hashes identify decisions and detect ordinary drift; they do not authenticate evidence against someone who can rewrite the evaluator. A passing check is acceptance under the declared policy, not permission to merge, publish, or deploy.

### Reusable GitHub Actions example

Copy the packaged `assets/ci/edd.yml` resource to `.github/workflows/edd.yml` in the adopting repository. In this source checkout it is available at [the workflow template](../src/edd_kit/assets/ci/edd.yml). Initialization does not install CI configuration automatically.

The template expects a committed `pyproject.toml` and `uv.lock` with the chosen EDD distribution in
an `eval` dependency group. The standard distribution includes the tested DeepEval backend. Pin the
release you reviewed and configure application-specific evaluation dependencies in the same locked
environment.

Call the reusable workflow from a project workflow with the relevant change and target:

```yaml
name: Feature acceptance
on: [pull_request]
permissions:
  contents: read
jobs:
  cancellation:
    uses: ./.github/workflows/edd.yml
    with:
      change: cancellation
      target: candidate
      upload-report: true # opt in only after checking the report's data sensitivity
```

The template runs fresh grader controls, candidate acceptance, and verification, then writes one
Markdown/JSON report with review state, blockers, expected versus observed behavior, controls,
configuration, criteria and application revisions, and fresh-versus-saved provenance. It needs no
baseline to assess standalone candidate acceptance. Actual reviewer approval remains part of your
repository's PR policy.

The default example has no model-provider secrets and is suitable for deterministic metrics and
local targets. Configure provider access only through your reviewed CI credential policy; an
unavailable provider remains a failed or incomplete check. Both uploads are off by default because
reports and raw evidence may contain case data. Enable `upload-report` for the consolidated bundle;
enable `upload-evidence` separately only when raw `.edd` records are appropriate.
