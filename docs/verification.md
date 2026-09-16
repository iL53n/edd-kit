# Release verification — EDD Kit 0.1.0

Observed 2026-09-15 against this worktree. This is verification of the local Python CLI/CI kit
and its documented cooperative-code scope, not certification of an adopter's application.
The [implementation contract](implementation.md) defines the scope; the
[security document](../SECURITY.md) defines the trust limits.

## Requirement-by-requirement evidence

| Requirement | Inspected implementation and actual evidence |
| --- | --- |
| 1. Package, CLI, reproducible DeepEval environment | Wheel and source distribution built with locked build dependencies; `twine check --strict` passed. Exact exported evaluator lock matches `uv.lock`. Hashed dependencies installed in isolated macOS environments and disposable Linux containers. Installed-wheel smoke exercised real CLI operations, resources and native grading. |
| 2. Initialization, skill-first authoring, brownfield, resume, safe sync | Scaffold tests exercised idempotence, existing-file preservation, custom change directories, path rejection and customization-preserving skill updates. The packaged Prepare/Build/Check skills now lead with the lightweight measurement loop and disclose strict acceptance as a separate branch. Independent examples remain in the [retained example](../examples/invoice-extraction/README.md). |
| 3. Native suite and execution policy | Contract, backend and execution tests exercised real `Case`/`Control`/`Suite` and DeepEval metrics, case and expectation provenance, deferred scenarios, empty control sets for development measurement, scenario coverage, trials, fresh factories, fixed configurations and strict policy types. Native G-Eval scored through a fake provider transport; this verifies native integration, not live model quality. |
| 4. Measurement, comparison, acceptance, identities, reports | Full workflows executed known-good, no-op and wrong-owner targets, failing and passing development measurements, compatible comparison, bundle-change refusal with case diffs, default Markdown/JSON reports, and the retained strict audit/acceptance flow. Evidence tests inspected durable observations, saved requirement semantics, target/runtime/environment identities, source digests and stale criteria/targets. |
| 5. Process, environment and execution safety | Real child-process tests covered separate credential allowlists, no expected-answer forwarding, bounded stdout/stderr, timeouts, cancellation/descendant cleanup, missing credentials, disabled implicit dotenv/telemetry, cost opt-in and unknown-cost handling. Native diagnostic credential redaction preserves structural identities. These controls are not hostile-code isolation or a provider-enforced spending ceiling. |
| 6. Fail-closed results | Decision and integrity tests exercised PASS/FAIL/ERROR/INCONCLUSIVE, critical failures, incomplete/duplicate/malformed observations, overflowed numbers, altered plans, forged summaries, checksum corruption, missing/stale review and stale target evidence. Verification recomputes the gate from evidence rather than trusting a saved green summary. |
| 7. Demo, starter and independent feature | `edd demo cancellation` runs outside the current repository and catches false success and unauthorized changes without claiming approval. Native tests also catch an unauthorized change later reversed. Starter cases declare synthetic provenance. Independent invoice and brownfield artifacts retain provenance and limitations. |
| 8. Workflow validation, fault tests, packaging, CI, trust/release docs | The current macOS/Python 3.13 suite passed 215 tests. Ruff, mypy, wheel/sdist build, strict metadata checks, the installed-wheel workflow, and retained-example replay passed. The earlier 185-test release baseline passed the six-environment matrix below; this measurement-loop delta has not yet been rerun across that complete matrix. |

## Executed compatibility checks

All environments used DeepEval 4.2.3 and the shipped hashed evaluator dependencies. The current
measurement-loop delta was verified on macOS ARM64 Python 3.13.5. The other rows record older
baselines, not a claim that the expanded suite ran there. Rerun the complete matrix before
publication.

| Environment | Full test suite | Installed distribution workflow |
| --- | --- | --- |
| macOS / Python 3.11 | 185 passed (pre-UX baseline) | PASS (pre-UX baseline) |
| macOS / Python 3.12 | 207 passed (pre-measurement baseline) | PASS (pre-measurement baseline) |
| macOS / Python 3.13 | **215 passed (current)** | **PASS (current)** |
| Linux / Python 3.11 | 185 passed (pre-UX baseline) | PASS (pre-UX baseline) |
| Linux / Python 3.12 | 185 passed (pre-UX baseline) | PASS (pre-UX baseline) |
| Linux / Python 3.13 | 185 passed (pre-UX baseline) | PASS (pre-UX baseline) |

The distribution smoke runs from an unrelated temporary project and verifies it imported the wheel,
not the editable source. It exercises the isolated guided demo, initialization, packaged
skills/lock, development measurement and comparison, review packet, separate domain/technical
decisions, workflow status, native audit,
genuine failing baseline, consolidated reporting, readiness, acceptance, deliberate defects,
target inference, stale evidence and an unreviewed draft. See
[the executable smoke](../scripts/smoke_distribution.py).

Ruff lint/format checks passed for source, tests and verification scripts; mypy passed for all
24 source files. Packaged-skill installation and reference copying passed in unit and wheel smoke.
An OSV-backed `uv audit --locked` checked 103 locked packages and reported zero known vulnerabilities
or adverse statuses on the date above. The experimental audit tool and vulnerability database
provide point-in-time evidence, not a security guarantee.

The optional coverage run reported 65% in-process statement coverage. Its isolated CLI/worker
subprocesses were not instrumented; those paths are exercised by end-to-end tests. This number
is not represented as complete execution coverage or used as a release-quality score.

The two engineer–SME pair pilot protocol is documented in [usability](usability.md). No real-user
sessions or live-provider invoice pilot were conducted in this implementation pass, so its
comprehension, correction and voluntary reuse targets remain product-validation work rather than
claimed evidence.

## Independent agent behavior

The independent agent's original preparation produced 12 invoice cases, three native graders and
20 proposed controls (six calibration, 14 validation). An unreviewed audit remained INCONCLUSIVE;
the genuinely executed null stub failed 16 of 36 observations. No production code or invented
human review was produced during that preparation-only request.

A separately authorized synthetic fixture review enabled the Build exercise. Ordinary process
tests went red→green; development evals exposed two field-ambiguity defects, followed by relevant
regression tests and implementation fixes. Fresh Check produced audit 14/14, application 36/36 and
verify PASS. Criteria/golden/metric hashes remained unchanged through implementation; Check did
not change the target. Resumption used a new CLI invocation and reread durable progress; it was
not an independent model-context-reset experiment.

The brownfield exercise began with only the existing parser and a fixed request for inline totals
with thousands separators. Prepare created six cases, three graders and eight controls. Audit was
8/8, input transport 6/6, and the current application failed seven of 18 observations without
execution errors. Its source hash was unchanged. No implementation of the extension was written.

These are synthetic workflow findings, not customer adoption evidence, actual human approval,
statistical generalization or live-provider validation. Historical run identities and portability
changes are recorded in the example README. [The independent-fixture replay](../scripts/smoke_examples.py)
rechecks the retained artifacts through an installed wheel with explicit test-only domain and
technical decisions in a temporary project; it does not substitute for the original agent exercise.

The current installed-wheel replay passed: invoice audit 14/14, genuine stub baseline with 16
violations and subsequent accepted application; brownfield audit 8/8 and seven expected existing-app
violations. Criteria and application immutability checks passed. Compute the artifact checksum from
the final downloaded build rather than relying on a mutable worktree document.

## Reproduce and release

Run the commands in [Contributing](../CONTRIBUTING.md#development-environment), then install the wheel and
hashed evaluator requirements into a separate environment. With its Python path:

```bash
python scripts/smoke_distribution.py --python /absolute/path/to/wheel-env/bin/python
python scripts/smoke_examples.py --python /absolute/path/to/wheel-env/bin/python
```

The exact lock check is also required in CI. Keep new dependency checks separate from executing
untrusted target code, and follow the release instructions in [CONTRIBUTING](../CONTRIBUTING.md).

Hosted GitHub Actions were **configured, not dispatched** in this workspace. The local Linux runs
are containers, not a claim that the hosted Ubuntu/macOS or x86-64 matrix has run. There was no live
provider call, package-index publication, GitHub release, commit, push, merge or deployment. Those
external actions remain separate from delivering the tested local kit. The temporary verification
containers were removed and the Colima VM started for them was stopped.
