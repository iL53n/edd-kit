# Develop through measurement

EDD uses coding-agent skills for authoring and a local CLI for repeatable execution. The first goal
is useful feedback, not a complete specification.

## 1. Initialize once

```bash
edd init --agent codex
```

Use `--agent claude` for Claude Code or `--agent none` for direct CLI use. Restart the agent
session after skills are installed.

## 2. Prepare a small measurement bundle

In agent chat:

```text
$edd-prepare Add an assistant that cancels an eligible order owned by the user.
```

The agent reuses existing specifications and repository context, then creates:

- a short behavior brief and stable requirements;
- a small, diverse scenario set;
- expected behavior and provenance;
- native DeepEval metrics;
- fixtures and target adapters.

Aim for roughly 10–20 initial cases when useful, but do not treat the number as proof of coverage.
Real traces and reviewed examples provide stronger domain evidence. Synthetic cases are useful for
boundaries and rare risks. Cases with unresolved expectations remain deferred and visible.

The equivalent terminal scaffold is:

```bash
edd prepare CHANGE --brief "Intended behavior"
edd inspect CHANGE --json
```

The scaffold is a draft; it cannot infer domain correctness from the brief.

## 3. Measure the starting behavior

```bash
edd measure CHANGE --target current --stage baseline --profile dev
```

Use a configured stub if the application does not exist yet and label it honestly. Save the
returned run ID. A behavior `FAIL` is a useful baseline when execution completed. Import failures,
malformed target output, and missing grader evidence are execution problems.

`edd status CHANGE` shows the default measurement workflow and next action. Use
`edd status CHANGE --acceptance` only for the strict gate.

## 4. Build in small loops

Use the build skill or work directly:

```text
$edd-build CHANGE
```

For each slice:

1. Choose one behavior or failure class.
2. Implement the smallest useful change.
3. Run ordinary software tests.
4. Measure the candidate.
5. Inspect cases, gaps, and the comparison.

```bash
edd measure CHANGE --target candidate --stage candidate --profile dev \
  --compare-to BASELINE_RUN_ID
```

The report separates execution status from behavior decision. It includes target identity,
observations, provenance, deferred cases, costs, and limitations.

## 5. Evolve the scenario set

When a result reveals a distinct failure class, the agent adds a small focused group of cases,
usually no more than five. Each addition records its source and why the expectation is believed.

Changing a case, metric, fixture, dependency, profile, or policy changes the measurement instrument.
EDD preserves older evidence and shows added, removed, and changed case IDs. It withholds numeric
deltas across different bundles. If a direct comparison matters, rerun both application versions
against the current bundle.

Do not lower thresholds or rewrite expectations merely to obtain a green result. Change them when
the product intent changed or evidence shows that the measurement was wrong.

## 6. Check and hand off

```text
$edd-check CHANGE
```

Or compare saved runs directly:

```bash
edd compare CHANGE --before RUN_ID --after RUN_ID
```

Hand back:

- execution status and behavior decision;
- important case-level failures;
- deferred cases and missing evidence;
- a numeric delta only when comparable;
- ordinary test results;
- links to Markdown and JSON reports.

After three loops without useful movement, stop and identify whether the blocker is application
behavior, evaluation quality, missing evidence, or a product decision.

## Optional strict acceptance

Use strict acceptance for release gates, high-risk workflows, compliance evidence, or explicit
review requirements. It adds reviewed good and bad grader controls, domain and technical decisions,
acceptance-profile execution, and verification:

```bash
edd status CHANGE --acceptance
edd audit CHANGE
edd review CHANGE --write
edd run CHANGE --target current --stage baseline --profile acceptance
edd check CHANGE --target candidate --report-dir .edd/CHANGE/acceptance
```

The reusable GitHub Actions template at
[`src/edd_kit/assets/ci/edd.yml`](../src/edd_kit/assets/ci/edd.yml) runs this strict branch. Reports
and raw evidence may contain sensitive data, so its artifact uploads remain opt-in.

## Resume and revise

Changes and run history live in the repository and `.edd/`. A later agent session reads the same
brief, bundle, status, and reports. Refine the same change while its user objective remains stable;
use a new change for a materially different objective.

Local records and hashes expose ordinary drift. They do not authenticate reviewers or protect
against someone who can rewrite evaluation code and history. See [Security](../SECURITY.md).
