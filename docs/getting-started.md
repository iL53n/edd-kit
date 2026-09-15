# Getting started with EDD Kit

This guide takes you from a fresh checkout to reviewed acceptance evidence for one feature. You
can use a coding agent to author and implement the feature, or run the CLI directly. In both cases,
EDD keeps the criteria, human decisions, grader audit, and application evidence separate.

## 1. Install EDD Kit

EDD Kit supports Python 3.11–3.13 on Linux and macOS. Install
[uv](https://docs.astral.sh/uv/getting-started/installation/), then install EDD as an isolated tool:

```bash
uv tool install edd-kit
edd doctor
```

The standard installation includes the tested DeepEval backend. `edd doctor` should report `PASS`.
The command remains available when you move into another repository; no EDD virtual environment
needs to remain active.

If the installation succeeds but `edd` is not found, add uv's tool directory to your shell and
restart it:

```bash
uv tool update-shell
```

To test an unpublished checkout, clone it and run `uv tool install ./edd-kit`. Contributors should
instead use the environment in [Contributing](../CONTRIBUTING.md#development-environment).

## 2. Try the offline demonstration

Before changing your application, run the deterministic cancellation demonstration:

```bash
edd demo cancellation
```

It should show that the graders accept the working candidate and reject two seeded defects. This
is an onboarding demonstration, not approval or evidence for your application.

## 3. Initialize your application repository

Change to the root of your application repository and choose an integration:

```bash
cd /path/to/your-application
edd init
```

Codex integration is the default. Use `edd init --agent claude` for Claude Code or
`edd init --agent none` if you will author the suite yourself. EDD creates `edd.toml`, an ignored
`.edd/` evidence directory, and—when selected—local agent skills. It preserves existing files and
reports conflicts instead of overwriting local customizations.

If skills were installed, restart the coding-agent session so it can discover them.

## 4. Prepare one feature

Choose a short change ID, such as `invoice-extraction`. IDs become directory names and are used in
every later command.

### Recommended: ask your coding agent

In Codex chat:

```text
$edd-prepare Extract the currency and final total from an invoice. Missing or ambiguous fields must be null.
```

In Claude Code, use `/edd-prepare` with the same request. The agent should inspect your application,
ask only consequential domain questions, and author the EDD suite before implementing the feature.

### Advanced: direct CLI alternative

Create a starter change:

```bash
edd prepare invoice-extraction \
  --brief "Extract invoice currency and final total; return null for missing or ambiguous fields"
```

Manual authoring requires Python and evaluation experience. Replace the example content under
`evals/invoice-extraction/` with your actual requirements,
cases, controls, and native Python graders. Connect the application under test in
`evals/invoice-extraction/contract.json`. See [Authoring EDD suites](authoring.md) for the complete
suite and target interfaces.

For either path, inspect the result before running evaluations:

```bash
edd inspect invoice-extraction
edd status invoice-extraction --verbose
```

Resolve configuration errors and missing coverage first. While work remains, `edd status`
identifies the next actor and command.

## 5. Generate the specialist review packet

Preview and then write the deterministic Markdown packet:

```bash
edd review invoice-extraction
edd review invoice-extraction --write
```

Open `evals/invoice-extraction/REVIEW.md`. A domain specialist should be able to review it without
reading Python or JSON. It contains:

- stable requirement, case, control, and grader identifiers;
- scenario inputs and expected behavior;
- acceptable alternatives and unacceptable outcomes;
- the domain rules each scenario covers;
- the evidence supplied to each grader control;
- separate domain and technical review checklists.

Commit the generated packet with the canonical criteria so the pull request shows exactly what was
reviewed:

```bash
git add evals/invoice-extraction
git commit -m "test: define invoice extraction acceptance criteria"
```

Do not hand-edit `REVIEW.md`; change the canonical criteria and regenerate it.

## 6. Record domain review

Copy the criteria digest shown near the top of `REVIEW.md`. After the specialist confirms that the
requirements and cases represent the business rule, record the decision:

```bash
edd review invoice-extraction \
  --area domain \
  --decision approve \
  --by "Reviewer name" \
  --note "The scenarios represent the intended invoice extraction rules" \
  --criteria-digest DIGEST_FROM_REVIEW_PACKET
```

If something is wrong or unclear, record feedback instead:

```bash
edd review invoice-extraction \
  --area domain \
  --decision request_changes \
  --subject case:ambiguous-total \
  --by "Reviewer name" \
  --note "This case must return null when two totals conflict" \
  --criteria-digest DIGEST_FROM_REVIEW_PACKET
```

`needs_discussion` is also available. Feedback is appended to `review.json`; it does not silently
rewrite the approved criteria.

After feedback that requires a criteria change, use this sequence:

1. Edit the canonical requirement, case, control, or grader—not `REVIEW.md`.
2. Run `edd review invoice-extraction --write`.
3. Inspect the rendered semantic diff and the repository diff:

   ```bash
   git diff -- evals/invoice-extraction/REVIEW.md
   ```

4. Record domain approval for the new digest.
5. Rerun `edd audit invoice-extraction`.
6. Record technical approval for the new digest.
7. Refresh the baseline before comparing it with the candidate.

A criteria edit invalidates both approval areas and the earlier audit, even if the original feedback
was technical. If discussion is resolved without changing criteria, a later explicit `approve`
event for that same digest closes the affected review area.

Technical reviewers can use the same feedback flow after the audit, for example:

```bash
edd review invoice-extraction \
  --area technical \
  --decision request_changes \
  --subject control:ambiguous-total-negative \
  --by "Reviewer name" \
  --note "Add a plausible conflicting-total failure that this grader must reject" \
  --criteria-digest DIGEST_FROM_REVIEW_PACKET
```

## 7. Audit the graders and record technical validation

After current domain approval, run the positive and negative controls:

```bash
edd audit invoice-extraction
```

A passing audit means the graders handled the declared controls. It does not prove that they are
universally reliable. Fix incorrect graders or controls, add independently contributed failure
examples, and rerun the audit until it passes.

An engineer can then confirm that the graders measure the approved domain expectations:

```bash
edd review invoice-extraction \
  --area technical \
  --decision approve \
  --by "Reviewer name" \
  --note "The controls and passing audit measure the approved expectations" \
  --criteria-digest DIGEST_FROM_REVIEW_PACKET
```

Commit `review.json` after the review decisions are recorded:

```bash
git add evals/invoice-extraction/review.json
git commit -m "test: record invoice evaluation review"
```

EDD requires both current review areas. Domain approval cannot substitute for grader validation,
and a passing grader audit cannot substitute for domain approval.

## 8. Capture the preimplementation baseline

Use an existing application, reference, or stub target configured under `targets` in
`evals/invoice-extraction/contract.json`:

```bash
edd run invoice-extraction --target current --stage baseline
```

`current`, `stub`, and `candidate` are examples, not reserved names. Use
`edd inspect invoice-extraction` to see the targets your contract actually defines. For a new
feature, the configured baseline target might be named `stub`. A baseline may legitimately exit
with code `1` (`FAIL`) when it proves the behavior is missing. Execution crashes, missing
credentials, and malformed evidence are not valid failing baselines.

If no meaningful baseline exists, record that explicitly:

```bash
edd baseline-unavailable invoice-extraction \
  --reason "This is a new provider-backed capability with no comparable implementation"
```

Check readiness:

```bash
edd status invoice-extraction
```

## 9. Implement the feature

With Codex:

```text
$edd-build invoice-extraction
```

With Claude Code, use `/edd-build invoice-extraction`. When working manually, implement the
application target and run its ordinary unit/integration tests alongside the development profile:

```bash
edd run invoice-extraction --target candidate --stage candidate --profile dev
```

Do not weaken expectations simply to make an implementation pass. If implementation reveals a real
domain ambiguity, return to the criteria, preserve the failing evidence, regenerate the packet, and
repeat both reviews and the audit for the new digest.

## 10. Run fresh acceptance and create the report

With Codex:

```text
$edd-check invoice-extraction
```

Or run the equivalent CLI workflow:

```bash
edd check
```

When exactly one change and application target exist, EDD infers both. In a repository with several
changes or targets, name them explicitly. Add report output and the application revision when you
want a CI-style evidence bundle:

```bash
edd check invoice-extraction \
  --target candidate \
  --report-dir .edd/invoice-extraction/report \
  --revision "$(git rev-parse HEAD)"
```

Commit the application first when the Git revision must identify its exact source. EDD still records
the target file digest and detects uncommitted target changes, but `git rev-parse HEAD` names only
the latest commit.

`edd check` runs a fresh grader audit, runs the candidate with the acceptance profile, verifies all
lifecycle gates, and writes `report.md` plus `report.json`. Read the Markdown report first:

```bash
open .edd/invoice-extraction/report/report.md  # macOS
# Linux: use your editor or desktop opener
```

The result and process exit codes are:

| Result | Meaning | Exit code |
| --- | --- | --- |
| `PASS` | Current evidence satisfies the declared acceptance policy | `0` |
| `FAIL` | Valid evidence shows a requirement violation | `1` |
| `ERROR` | Configuration, execution, or evidence integrity failed | `2` |
| `INCONCLUSIVE` | Required review, coverage, or fresh evidence is missing | `3` |

To inspect already saved evidence without running the application or graders again:

```bash
edd verify invoice-extraction
edd report invoice-extraction --acceptance \
  --output-dir .edd/invoice-extraction/saved-report
```

The report labels newly executed and reused evidence separately.

## 11. Add the optional CI workflow

Copy the packaged workflow into the application repository:

```bash
mkdir -p .github/workflows
cp /path/to/edd-kit/src/edd_kit/assets/ci/edd.yml .github/workflows/edd.yml
```

Your application must provide a locked `eval` dependency group containing the reviewed EDD Kit
distribution and application evaluation dependencies. Pin the reviewed EDD release in the
application's `pyproject.toml`:

```toml
[dependency-groups]
eval = [
  "edd-kit==0.1.0",
]
```

Update the version only after reviewing a newer release. Add any target-specific dependencies to
the same group, and commit the resulting lockfile:

```bash
uv lock
uv sync --locked --group eval
git add pyproject.toml uv.lock
git commit -m "build: lock EDD evaluation environment"
```

The packaged workflow runs that same locked group. Call it from an existing pull-request workflow:

```yaml
name: EDD acceptance
on: [pull_request]
permissions:
  contents: read

jobs:
  invoice-acceptance:
    uses: ./.github/workflows/edd.yml
    with:
      change: invoice-extraction
      target: candidate
```

Report and raw-evidence uploads are both off by default because they may contain sensitive case
data. After inspecting a representative report, opt in explicitly if appropriate:

```yaml
jobs:
  invoice-acceptance:
    uses: ./.github/workflows/edd.yml
    with:
      change: invoice-extraction
      target: candidate
      upload-report: true
      # upload-evidence: true  # Separate opt-in; may expose raw inputs and outputs.
```

CI reruns checks; it does not create human approval or grant permission to merge or deploy.

## 12. Resume or revise later

Start with status whenever you return to a change:

```bash
edd status invoice-extraction
edd status invoice-extraction --verbose
```

EDD retains accepted suites for regression use. Its identities enforce these lifecycle rules:

- criteria changes invalidate review, audit, candidate, and baseline evidence used for comparison;
- changes to files declared by the selected application target invalidate candidate evidence;
- missing scenario coverage cannot produce acceptance;
- schema-v1 combined review stamps remain visible but require review under the two-area lifecycle.

Run `edd sync --agent codex` to preview updated managed skills and add `--apply` only after reviewing
the changes. Locally customized skill files are reported as conflicts and preserved.

## Where files live

```text
your-application/
├── edd.toml
├── evals/invoice-extraction/
│   ├── brief.md
│   ├── contract.json
│   ├── cases.json
│   ├── controls.json
│   ├── suite.py
│   ├── REVIEW.md       # generated specialist packet; commit this
│   └── review.json     # versioned review decisions; commit this
├── targets/invoice-extraction/
│   └── candidate.py
└── .edd/               # local runs, reports, and history; ignored by Git
```

The criteria and review files are repository artifacts. `.edd/` contains local evidence and may
include sensitive inputs or outputs.

## Common problems

### `edd` is not found

Run `uv tool update-shell`, restart the shell, and try `edd --help`. Confirm installation with
`uv tool list`.

### `edd doctor` reports missing DeepEval

Reinstall the complete isolated tool:

```bash
uv tool install --reinstall edd-kit
```

### Review is stale

Criteria changed after approval. Run `edd review CHANGE --write`, inspect the semantic diff, and
record new decisions for the new digest.

### Candidate evidence is stale

The application target changed after its last run. Run `edd check CHANGE --target TARGET` again.

### Audit evidence is stale

The criteria, grader, controls, or evaluation runtime changed. Confirm the current domain decision,
run `edd audit CHANGE`, and record technical approval for the current digest.

### Baseline evidence is stale

The criteria or baseline target changed. Rerun the configured baseline target with `--stage
baseline`, or record a new explicit `baseline-unavailable` reason when no comparison is meaningful.

### Provider credentials are missing

Configure only the environment-variable names declared by the suite. Provider-backed graders also
require a positive cost policy and `--allow-paid`. Missing credentials remain non-passing; never
commit secrets or place production credentials in reports.

### You do not know what to do next

Run:

```bash
edd status CHANGE --verbose
```

For deeper detail, continue with the [workflow guide](workflow.md), [authoring reference](authoring.md),
and [security boundaries](../SECURITY.md).
