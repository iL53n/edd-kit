# Security and trust boundaries

EDD Kit runs evaluation code and application targets supplied by the adopting project. It is designed for cooperative, reviewed code on Linux and macOS. Its process limits and environment handling reduce accidental interference; they are not a sandbox for hostile code.

## What a passing result means

A passing result means the recorded observations satisfy the configured acceptance policy and its evidence requirements. It does not prove complete behavioral coverage, production reliability, or permission to deploy.

Evaluation and target digests identify recorded inputs and detect ordinary changes. They do not authenticate the author of a run or prevent someone who can edit the evaluator, criteria, review packet, review log, or report from fabricating evidence. Committed `REVIEW.md` and `review.json` files are portable declarations of what was reviewed and decided, not signatures or substitutes for repository approval rules.

Target metadata, tool traces, and reported state are not independently attested. For stateful requirements, a reviewed fixture or service boundary must collect the observations that justify the claim. A candidate's own success field is not authoritative evidence that the operation happened. The bundled cancellation example uses synthetic data and a cooperative fixture; it supplies no assurance about an adopter's environment.

## Executing project code

Python suite modules and custom metric factories execute as code. Targets execute in separate processes with bounded time and output and an explicit environment allowlist. Those processes still use the caller's operating-system identity and may access files or network services allowed to that identity. An environment allowlist is neither container isolation nor a network policy.

Run untrusted project code only in an independently provisioned environment appropriate for that threat model. Keep production credentials and privileged deployment tokens outside the evaluation environment. Declare only the target and evaluator credential names the configured run needs.

## Data and network access

Local run and review history lives under `.edd/`; initialization adds an ignore rule for that directory. Prepared criteria, the specialist-readable `REVIEW.md`, and the portable `review.json` decision log live in the change directory and may be committed. Treat cases, fixtures, outputs, tool arguments, metric explanations, reviewer rationale, and reports as potentially sensitive data.

EDD disables its DeepEval integration's automatic dotenv loading and telemetry/reporting path. Explicitly configured model graders and application targets can still send inputs to their providers, incur charges, or log data through custom code. Review provider settings, data handling, and execution budgets before enabling those integrations.

Configuration and evidence should contain credential references rather than credential values. Redaction and filtered error messages do not make arbitrary application output safe to share. Inspect reports before attaching them to an issue or enabling CI evidence uploads. Removing local files does not remove previously uploaded artifacts or provider-side records.

## CI defaults

The repository workflows use read-only repository permissions, pinned action revisions, ephemeral hosted runners, and no provider or publishing credentials. They use `pull_request`, not privileged execution of pull-request code through `pull_request_target`.

The optional adopting-project workflow requires a current, committed review packet, current domain and technical approvals, a passing grader audit, and fresh candidate evidence; it does not create approval during CI. Consolidated reports and raw evidence are separate, opt-in uploads. Required checks and actual PR approvals remain repository settings managed by the adopter. Provider-backed evaluations require a separately reviewed credential arrangement; missing credentials must remain a non-passing evaluation outcome.

The release-artifact workflow checks and builds distributions for manual inspection. It does not
publish, create a GitHub release, or deploy an application. The separate tag-triggered publish
workflow receives an OIDC publishing identity only in its final `pypi` environment job, after the
tagged revision passes CI and the built distributions pass an isolated tool-install smoke test.

## Reporting a vulnerability

Use the repository's **Security → Advisories → Report a vulnerability** entry when private reporting is enabled. Otherwise, contact a maintainer through a private contact method listed on their public profile. If no private route is available, open an issue requesting one without including exploit details, credentials, or private evaluation data.

Include the EDD version, Python and operating-system versions, affected command, expected trust boundary, and a minimal reproduction using synthetic data. Reports about criterion bypass, secret disclosure, unsafe path handling, process cleanup, dependency compromise, or falsely accepted incomplete evidence are relevant. Maintainers may ask whether the issue reproduces on the current release.
