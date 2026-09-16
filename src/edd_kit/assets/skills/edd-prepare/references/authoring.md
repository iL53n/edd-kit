# Native suite authoring

Read this when authoring or revising an EDD pipeline. `edd prepare` creates a draft; the coding
agent supplies the domain-specific specification, cases, metrics, controls and target adapter.
An ordinary CLI scaffold does not infer correctness from a natural-language brief.

## Project artifacts

`edd.toml` contains `schema_version = 1` and `changes_dir = "evals"` (a safe relative directory).
Each change has a `contract.json`, a Python suite entrypoint, datasets, a brief, and any grader or
fixture helpers. Everything in the change directory is fingerprinted except generated Python
bytecode and `review.json`. Put independently changing application code outside that directory.
The generated `eval-requirements.lock` pins the tested evaluator dependencies with package hashes;
install it into a dedicated evaluator environment and install the EDD wheel separately. Extend and
regenerate that lock when the authored suite introduces dependencies. The application's environment
is configured independently through the target command.

The short brief records intent, exclusions, consequential decisions, representative acceptable and
unacceptable examples, and remaining risks. Reuse existing Spec Kit/OpenSpec/project specifications
by reference. Treat the brief as a living hypothesis, not a promise that all design questions are
settled before implementation. Include external specifications and evaluator helpers in `artifacts`
so edits make earlier evidence stale. Preserve existing application architecture in brownfield
projects.

## Contract

Example for a structured extraction feature; replace the semantics and target files for the task:

```json
{
  "schema_version": 1,
  "change": "invoice-extraction",
  "title": "Extract invoice totals without inventing missing amounts",
  "suite": "suite.py:build_suite",
  "artifacts": ["uv.lock"],
  "requirements": [
    {"id": "correct-total", "description": "Return the source total or null when absent",
     "critical": true, "pass_rate": 1.0, "min_cases": 2}
  ],
  "profiles": {
    "dev": {"trials": 1, "grader_repetitions": 1, "max_observations": 100,
            "max_cost_usd": 0, "timeout_seconds": 60},
    "acceptance": {"trials": 3, "grader_repetitions": 1, "max_observations": 1000,
                   "max_cost_usd": 0, "timeout_seconds": 120}
  },
  "evaluator_env": [],
  "targets": {
    "candidate": {"kind": "application", "command": ["python3", "app/target.py"],
                  "files": ["app/target.py", "app/extractor.py"], "env": [],
                  "timeout_seconds": 10},
    "stub": {"kind": "stub", "command": ["python3", "app/stub.py"],
             "files": ["app/stub.py"], "env": [], "timeout_seconds": 10}
  }
}
```

Reference actual files only; `artifacts` are relative to the project root and may name files or
directories. Include the evaluator dependency lock and every evaluator dependency outside the
change directory. `targets.*.files` likewise covers application prompts, source, dependencies,
and nonsecret configuration. External application/model/index versions belong in target `version`
and controlled target configuration. A version string is a declared identity, not remote attestation.

`critical` means any observed failure violates acceptance. `pass_rate` is the required proportion of
successful grading observations for a noncritical requirement; `min_cases` counts unique scenarios,
not trials or grader repetitions. Thresholds belong in the native metric factory. A score-only metric
cannot establish a passing gate. Different profiles are not directly comparable.

## Python interface

Export `build_suite()` from the declared Python file. Import `Case`, `Control`, and `Suite` from
`edd_kit`, and use actual DeepEval `LLMTestCase` and fresh `BaseMetric` subclasses/factories:

```python
from deepeval.test_case import LLMTestCase
from edd_kit import Case, Control, Suite


def build_suite():
    return Suite(
        cases=[
            Case(
                case_id="missing-total",
                test_case=LLMTestCase(
                    input="Invoice with no total", expected_output='{"total":null}'
                ),
                requirements=("correct-total",),
                profiles=("dev", "acceptance"),
                fixture={},
                description="An invoice omits an explicitly labelled total.",
                expected_behavior="Return null rather than guessing a total.",
                acceptable_alternatives=("Equivalent valid JSON whitespace is acceptable.",),
                unacceptable_behaviors=("Copy a subtotal or invent a value.",),
                source="anonymized production trace",
                expectation_source="reviewed invoice-processing policy",
                deferred_reason=None,
            ),
            # Add the other independently sourced domain scenarios required by coverage policy.
        ],
        controls=[
            Control(
                control_id="fabricated-total",
                requirement_id="correct-total",
                test_case=LLMTestCase(
                    input="Invoice with no total",
                    actual_output='{"total":25}',
                    expected_output='{"total":null}',
                ),
                expected_pass=False,
                source="Reviewed worked example for missing source evidence",
                partition="validation",
                case_id="missing-total",
                rationale="A plausible fabricated total must be rejected.",
                contributed_by="Invoice evaluation engineer",
                independent=True,
            ),
            # Each requirement needs relevant reviewed positive AND negative validation controls.
        ],
        metrics={"correct-total": make_total_metric},  # Define this fresh-metric factory.
    )
```

The shortened example is intentionally incomplete. Author the domain metric and representative
cases before measuring; add controls before expecting the strict audit to pass. Load datasets using
paths relative to `__file__`.
Every identity is stable and unique. Every case maps to requirements, includes specialist-readable
behavior, and every requirement has a native metric factory. Controls exercise their mapped metric,
carry explicit provenance and rationale, and include an independently authored negative example;
rejection by an unrelated check does not establish sensitivity to the intended defect.

Each deterministic metric's `measure()` sets a fresh finite `score`, boolean `success`, textual
`reason`, clears `error`, and sets `evaluation_cost = 0.0` for that measurement. Implement the native
`is_successful()` and `__name__` interface. Factories return a new metric; EDD resets stale result
attributes before measuring. Use semantic grading when meaning matters and deterministic checks
when exact structure, authorization, state, or contractual limits matter. Do not turn every valid
natural-language response into an exact-string test.

Controls with `partition="calibration"` are tuning material, not validation evidence. Validation
controls need both expected labels for each requirement, meaningful source provenance, and actual
review. When a validation example influences tuning, reclassify it and obtain new validation
examples. Local partitions are visible to the coding agent; they are not protected holdouts.

Cases may use `source` to identify where the input came from and `expectation_source` to identify
why the expected behavior is believed. Typical values are production trace, manually authored,
reviewed policy, and synthetic. If an expectation is unresolved, set `deferred_reason`; EDD keeps
the case visible but does not execute or grade it. Resolve deferred cases in small batches as
evidence becomes available.

## Target process interface

Each case/trial launches the configured command without a shell, from the project root. The target
reads one JSON object from stdin and returns one JSON object on stdout, then exits. Diagnostics
belong on stderr. Both output and time are bounded; background descendants are cleaned up.

Request fields: `case_id`, `input`, optional `context`, `fixture`, and `trial`. Expected outputs,
expected tool calls, grader code, and grading metadata are not sent to the target. `fixture` contains
initial environment inputs, not the answer key. Reset state for every trial through the adapter.

Required response: `{"actual_output": "..."}`. Optional fields: `context`, `retrieval_context`
(lists of strings), `tools_called` (native tool-call dictionaries), and `metadata` (an object).
EDD constructs a fresh native test case with the expected evidence from the suite and observations
from this response. Reserved metadata includes the case identity, fixture and measured elapsed
time; target metadata cannot replace those evaluation inputs.

For tool/state requirements, the adapter collects authoritative state and action history through
the fixture/service interface. A model's own success claim is not authoritative state. The offline
cancellation template illustrates state collection in a cooperative toy application; it does not
attest a customer's collector. If collection remains unchecked, report that gap and add reference
and deliberately defective integration checks before claiming live acceptance.

Target failures to start, malformed output, missing evidence and infrastructure timeout are errors,
not proof that a known defect was exercised. A contractual response-time violation can instead be
evaluated through an explicit latency metric when valid completion evidence is available.

## Execution and costs

Run `edd inspect CHANGE --json` before execution to inspect case/control mappings and planned work.
Execution refuses plans beyond `max_observations`. Each target trial is fresh; grader repetitions
do not turn one scenario into multiple independent scenarios. EDD does not retry failed observations
into success or count cached responses as fresh independent trials.

Use `edd measure` for the ordinary development loop. It records a run and writes a human Markdown
report plus machine-readable JSON. Use controls, review records, `edd audit`, `edd verify`, and
`edd check` when the task requires strict acceptance.

Native model graders require explicit provider configuration in their factory, named environment
references in `evaluator_env`, a positive cost policy, and the command's `--allow-paid` opt-in.
Target provider credentials are separately declared in `targets.*.env`. Only declared credentials
are forwarded; never place values in contracts, briefs, shell command arguments, or datasets.
Automatic dotenv loading, DeepEval telemetry, and hosted reporting are disabled by the runner.

Observed grader cost is reported and checked between calls. Provider billing can exceed an estimate
or one remaining-call budget, so this is not a provider-enforced dollar ceiling. Unknown cost is an
explicit gap. Configure provider-side limits for hard spending enforcement. Target application
provider cost is outside DeepEval grader cost unless a separate contractual check measures it.

## Review, baseline, and iteration

Use `edd review CHANGE --write` to generate the committed specialist packet. Record domain feedback
or approval with `--area domain --decision ... --by NAME --note TEXT --criteria-digest DIGEST` and an
optional requirement/case subject. Feedback is an event in `review.json`; it never mutates criteria.
After explicit canonical edits, regenerate the packet and inspect its semantic diff. Run
`edd audit CHANGE`, then record technical validation with the same form using `--area technical`.
Technical approval requires a current passing audit. Repository protection supplies approval
authority; neither a skill nor the local record authenticates a reviewer or proves chronology.

Then run `edd run CHANGE --target NAME --stage baseline --profile acceptance`.
An expected FAIL from a valid stub/current application is useful baseline evidence. Import errors
and broken collectors are not feature baselines. A greenfield stub/reference baseline is labeled
as such; it does not measure the future product. An unavailable application baseline must remain
an explicit limitation rather than a fabricated score.
Use `edd baseline-unavailable CHANGE --reason TEXT` to record that limitation; it does not create
observations or a comparison score and does not convert an errored run into a successful baseline.

Implement against `--profile dev`, then run full candidate acceptance and `edd verify CHANGE`.
Only a current application target can support acceptance; replayed controls, references and stubs
cannot. Direct comparison requires the same evaluation bundle and profile. A candidate may pass
without a comparable baseline, or improve while still failing acceptance.

Changing a requirement, golden, metric, fixture, dependency or threshold makes affected review/run
evidence stale. Show a semantic diff and reason, preserve custom work, review revised expectations,
and rerun affected audits/baselines. Keep acceptance suites executable after the feature is complete.
