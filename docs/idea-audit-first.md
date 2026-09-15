# EDD Kit: check the acceptance criteria before trusting the change

Status: product proposal, revised 2026-09-15. No implementation or customer validation yet.

## Recommendation

Run a small pilot around one job: help an engineer discover which known failures their existing LLM evaluation suite incorrectly accepts. Use that evidence to introduce acceptance criteria before the next implementation change.

The original vision remains:

> Before implementing a meaningful behavior, define its acceptance criteria and demonstrate that the checks distinguish reviewed good outcomes from relevant bad outcomes.

The first product promise should be narrower:

> EDD Kit shows which reviewed failures your evals miss, and records whether a proposed change satisfies the checked requirements.

Proceed with a prototype only after the manual workflow produces actionable findings. Treat a standalone business, broad backend support, and enforced delivery infrastructure as hypotheses requiring further evidence.

The [evaluation](evaluation.md) explains the tradeoffs; [research](research.md) records the alternatives. The [original draft](idea-original.md) is preserved.

## 1. The customer and the moment of need

Initial user hypothesis: an engineer responsible for an LLM feature who already has an executable evaluation suite, uses a coding agent for changes, and has seen incorrect behavior pass that suite.

The recurring trigger is a prompt, model, tool, or application change. The engineer needs to answer:

- Would our checks catch the failure we care about?
- Did this change improve the requested behavior without breaking another requirement?
- What still needs review before we accept the change?

Start with teams that can provide an existing runner, a reproducible missed failure, and someone able to judge the expected outcome. Teams without these inputs first need evaluation setup or domain work; that is a different onboarding cost.

The initial user is the engineer. A possible later buyer is the engineering lead responsible for release quality. Willingness to use a local tool and willingness to pay for team infrastructure must be tested separately.

A synthetic order-cancellation assistant is the demonstration, not the definition of the customer.

## 2. What is already available

The methodology and most underlying capabilities already have precedents.

| Alternative | Verified overlap | Implication |
| --- | --- | --- |
| Promptfoo | Assertions, replay of precomputed outputs, and a documented judge-calibration workflow with human labels and holdout validation. | Use its execution layer; calibration alone cannot establish differentiation. |
| DeepEval / Confident AI | Evaluation metrics, coding-agent skills, and hosted metric alignment with false-pass and false-fail analysis. | Agent packaging and grader alignment are already offered together. |
| ECC and Awesome Copilot skills | Existing evaluation workflows for coding agents. | A skill and a new workflow name are insufficient reasons to switch. |
| Spec Kit test-first governance preset | Acceptance tests, traceability, and workflow gates. | Test-first governance is an existing alternative. |

Sources: [Promptfoo assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/), [configuration](https://www.promptfoo.dev/docs/configuration/reference/), [judge calibration](https://www.promptfoo.dev/docs/guides/llm-as-a-judge/); verified DeepEval and workflow references are in the [research comparison](research.md).

The remaining product hypothesis is about the whole task: can a small tool connect a real missed failure to a checked requirement and useful change evidence with less effort than these tools plus a short script?

Potential value comes from preserving the link between requirement, reviewed controls, actual grader, and later change report. Whether users need a separate product for this is unresolved. If an existing backend plus a checklist performs equally well, ship an integration or contribute upstream.

## 3. First-use experience

Ask the user to bring one behavior their current evaluation incorrectly accepted.

Example: the assistant says an order was cancelled, while the order remains active. The existing response grader accepts the answer.

Together, create a small set of reviewed controls. A control is an example whose expected grading result is known.

| Control | Expected result | What it checks |
| --- | --- | --- |
| Correct cancellation, accurate confirmation | Accept | Legitimate success is recognized |
| Same valid outcome, different wording | Accept | The check allows acceptable alternatives |
| Confirmation with no state change | Reject | A success claim cannot substitute for the outcome |
| A different customer's order is changed | Reject | A critical state violation is detected |
| Unauthorized request rejected without changes | Accept for that scenario | Correct refusal is recognized |

Authorization belongs in deterministic application checks. The evaluation checks that behavior; an LLM judge must not become the access-control mechanism.

Run the existing graders against these controls. Report each mismatch and the requirement it affects. A bad example rejected by an unrelated formatting check does not demonstrate that the authorization check works.

Illustrative output, not a measured result:

```text
Acceptance-check audit: cancellation

Valid controls accepted:       3 / 3
Invalid controls rejected:     1 / 2

Missed failure:
  fabricated-confirmation
  Expected: reject on truthful_confirmation
  Observed: accepted
  Evidence: response says "cancelled"; order state is "active"

Audit: FAIL
Scope: saved evidence only; live state collection has not been checked.
```

Improve the check, rerun both good and bad controls, and retain the example for the next change. The report should identify a concrete blind spot, not offer a universal quality score.

## 4. Keep three kinds of evidence distinct

**Grader checks:** replay reviewed outputs and evidence through the same grader configuration used for application evaluations. These show whether the grader handles those examples correctly.

**Harness checks:** run a valid reference and a deliberately defective variant through a fixed sandbox. These check that inputs, state collection, reset, and grading work together. Replay alone cannot establish this.

**Application evaluations:** run the actual candidate on development or acceptance cases. These provide evidence about that candidate under those conditions.

For a stateful feature, collect state through the fixture or service boundary. When a requirement forbids an action, also inspect authoritative action history: final state can conceal an unauthorized change later reversed. A candidate-authored JSON field claiming success is not authoritative state. Anthropic's evaluation guidance explicitly separates an agent's transcript from the resulting environment state. [Source](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

A challenge must exercise the relevant defect. If a defective variant never reaches the affected operation, or crashes before it, record it as unexercised or an execution error. Do not count it as a detected defect.

The first release supports replay over existing evidence and one synthetic harness example. General code mutation and arbitrary customer sandboxes come later, if integration demand justifies them.

## 5. The eval-first workflow

Once an initial audit is useful, apply the discipline to each new behavior:

```text
Describe intent
  → Review examples and counterexamples
  → Check graders and the required evidence collection
  → Record the current application's baseline
  → Implement the behavior
  → Compare baseline and candidate under the same criteria
  → Review failures, uncertainty, and acceptance evidence
```

The lightweight acceptance contract contains:

- The behavior and its scope, including explicit exclusions.
- Stable requirement IDs and their native backend assertions.
- Development cases, reviewed controls, and their expected outcomes.
- The evidence each grader needs and where it comes from.
- Per-requirement thresholds, minimum coverage, and trial policy.
- References to the evaluation configuration, fixtures, and dependencies.

Keep native datasets and grader configuration in their existing backend. Add only the metadata needed for traceability and audit decisions. Do not create another universal evaluation language.

A short product spec records intent that examples cannot fully enumerate. Controls demonstrate selected distinctions; they do not certify complete coverage.

### Baselines and changing requirements

The baseline can be the current application, a minimal executable stub, or a reviewed reference. An import failure does not demonstrate that the requested capability is missing.

Some baseline cases should already pass. A harmless no-op may correctly pass a restriction against unauthorized changes. If the existing implementation already satisfies the requirement, record that no behavior change is needed.

When criteria change, record the reason, review affected controls, and run both baseline and candidate under the new evaluation version. Preserve previous evidence. Never present scores from different criteria as a direct improvement.

Local review records document a decision. They do not provide externally enforced approval.

## 6. Minimum coherent release

Start with one supported, pinned Promptfoo version and one agent integration. This is a provisional implementation choice: change it before building if pilot users already use another backend.

Promptfoo can run assertions against precomputed provider outputs, making replay a plausible first integration. Pin the tested backend version and fail explicitly on unsupported result formats. [Source](https://www.promptfoo.dev/docs/configuration/reference/)

The deliverables are:

1. A local audit command that reuses native graders, validates requirement/control mappings, and reports false passes, false failures, missing evidence, and errors.
2. A small manifest linking existing files, requirements, controls, and run policies.
3. A comparison report for baseline and candidate runs, with version checks and links to individual evidence.
4. One coding-agent skill to help draft and explain artifacts. Ordinary code computes audit decisions.
5. One runnable cancellation demo with saved controls, a fake order store, and explicitly faulty variants.

Proposed command surface; these commands do not exist yet:

```bash
edd init --backend promptfoo --config promptfooconfig.yaml
edd audit --contract acceptance.yaml
edd compare --contract acceptance.yaml --base runs/base.json --candidate runs/candidate.json
```

For the initial comparison, the existing backend produces runs through a documented wrapper that records execution metadata. Imported files without that metadata remain inspectable but cannot produce an acceptance result. Overall acceptance also requires a passing control audit for the same evaluation bundle; a missing, stale, or failed audit cannot support acceptance even when application scores pass.

Each report identifies actual candidate execution, reference/stub execution, or replay, and the evidence-collection checks exercised. Saved evidence cannot establish live application acceptance. The demo's harness checks provide no assurance about a customer's harness; unchecked collection remains an explicit acceptance gap.

The kit writes local reports. It does not need a hosted account. Running model graders can still incur provider costs; the command should expose configured limits and estimate work before execution.

Defer multiple backends, a new coding agent, automatic prompt optimization, general mutation infrastructure, hidden-case hosting, approval services, deployment control, dashboards, and a Spec Kit extension. Add an extension when pilot users' existing workflow calls for it.

## 7. Decision and evidence rules

Separate application results from audit results. A control expected to fail its application grader is a successful audit observation when it actually fails for the expected reason.

| Outcome | Meaning |
| --- | --- |
| PASS | All required observations completed and satisfied the declared policy |
| FAIL | Completed observations decisively violate the declared audit or application policy |
| INCONCLUSIVE | No decisive failure is established, but required evidence or coverage is insufficient |
| ERROR | Configuration, execution, or result integrity is invalid |

Retain execution status and observed violations separately. A critical violation establishes FAIL immediately; noncritical trial failures are assessed under the declared threshold. Once valid evidence decisively violates a policy, the decision remains FAIL even when other cases error; show those errors as incomplete coverage. Otherwise use ERROR for invalid execution, INCONCLUSIVE for insufficient evidence, and PASS only for a complete satisfied policy.

Report control-audit status, candidate acceptance, and baseline-to-candidate change separately. Baseline failures do not fail the candidate. A candidate can improve while still failing acceptance, or pass without improving.

Only PASS returns a successful gate exit code. Explicit requirements include:

- Empty datasets, missing required assertions, missing run metadata, duplicate result identities, and silently skipped required cases cannot pass.
- Confirm expected versus completed case, trial, and grader counts.
- Evaluate critical requirements separately; aggregate quality cannot offset a violation.
- Validate expected labels and their reviewer/source provenance. Disputed labels require review.
- Mark cases inapplicable explicitly; an inapplicable case does not count toward minimum coverage.
- Report the reason a control failed, not just a suite-level failure.
- Treat malformed model-judge output as an error; do not coerce it into a pass.
- Distinguish a candidate exceeding its contractual deadline from evaluator infrastructure timing out; the former is an application failure and the latter an execution error.
- Validate changes to every referenced evaluation artifact, including fixtures, imported grader code, and the dependency lockfile.

A run should record the candidate revision and any dirty-worktree digest; resolved target configuration; contract, dataset, grader, and fixture digests; backend and wrapper versions; resolved overrides; model settings and resolved identifiers where available; execution profile; attempts and retries; and per-observation evidence references. Record nonsecret configuration and credential references, never raw credentials. A local digest identifies content and detects ordinary drift. It does not authenticate who produced a result or guarantee exact replay of a mutable remote service.

Separate the changing target from the evaluation bundle, even when the backend stores them in one configuration file. The application's prompt, model, and code may change; cases, judge configuration, grading logic, fixtures, and policy remain fixed for a direct comparison. Record both sets of resolved inputs. A comparison using a different evaluation bundle must explain the mismatch and request a new baseline run.

### Stochastic results

Distinguish unique scenarios, model trials, grader repetitions, and infrastructure retries. Cached replay does not count as a fresh independent trial.

Show false-pass and false-fail counts separately, with denominators. Use reviewed controls for calibration and a separately selected set for validation. Once examples influence tuning, treat them as development data.

Three trials may reveal instability during development; they do not establish production reliability. State sample size, grouping, and uncertainty. Keep first-attempt results and the cost of retries visible. A budget or rate limit that prevents required observations leaves the run incomplete.

## 8. Trust and enforcement boundary

Version 0 supports cooperative developers and coding agents. It detects mistakes, missing evidence, and ordinary criteria drift. Local files and hashes cannot prevent a contributor from changing the checker or fabricating a report.

A later enforced merge gate would require a separately controlled evaluation bundle and publisher, isolated candidate execution, and grading of evidence collected outside candidate control. Protect criteria changes through normal repository review and reevaluate the current candidate revision after changes.

Required CI checks alone are insufficient: GitHub documents that successful, skipped, and neutral check states may satisfy protection, and supports restricting a check's source to an expected app. A future integration must publish explicit failure for every non-PASS decision and verify its workflow cannot silently skip evaluation. [Source](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

Candidate code must not execute with evaluator secrets or authority to publish its own acceptance result. GitHub warns about privileged workflows that execute untrusted pull-request code. [Source](https://docs.github.com/en/actions/reference/security/secure-use)

Held-out cases require actual access separation and controlled feedback. Another agent reviewing the same materials is not independent ground truth. Neither feature is required to demonstrate the local audit's initial value.

## 9. Validation before a platform

Use a manual pilot to test the uncertain parts first. The numbers below are proposed decision rules for a small pilot, not market evidence or statistically validated thresholds.

| Stage | Activity | Proposed criterion to continue |
| --- | --- | --- |
| Problem discovery | Interview five engineers with existing LLM evals; request their latest missed failure and current command | At least three provide a real example and a reviewer |
| Assisted audit | Reproduce the failure; review good/bad controls; audit and repair one check using existing tools | At least three close a reproducible acceptance gap while retaining valid behavior, with median combined hands-on effort under 60 minutes |
| Repeat use | Observe the next eligible change within four weeks of each audit | At least two reuse the workflow without a founder reminder; no eligible change means insufficient opportunity, not rejection |
| Incremental value | Compare the kit with the same backend, labels, and a short calibration/checklist script | At least two users prefer the kit for a concrete reduction in work or missed issues |
| Commercial discovery | Offer a specifically scoped paid pilot | At least one accepts before building paid team infrastructure |

Log fixture preparation, reviewer time, integration time, model cost, false alarms, and maintenance. Separate one-time setup from recurring work. Track newly discovered blind spots separately from known failures successfully converted into checks. If an audit finds no blind spot, retain that result; do not manufacture a defect to make the product look useful.

For a later controlled study, compare matched task groups under equal agent settings and budgets. Independently prepared acceptance cases should be frozen before either workflow runs. Report time to independently accepted change, escaped defects, reviewer effort, and maintenance cost. A small pilot supplies directional evidence, not a general efficacy claim.

## 10. Distribution, economics, and stop criteria

Distribution hypothesis: a runnable example showing a real false pass, the corrected check, and its evidence will attract the right users. Reach them through the evaluation backend and coding-agent workflow they already use.

Commercial hypothesis: a local utility can lead to paid work around shared reviewed cases, maintained integrations, or managed verification. Test which recurring task someone will fund before choosing a hosted product.

The expensive work may be labeling and building realistic fixtures. If every adoption needs bespoke domain integration, this may be a service or a backend extension. Usage-based model bills are not evidence that customers will pay an additional platform subscription.

Continue as a focused tool if users repeatedly find actionable blind spots and reuse it during changes.

Keep it as a skill, template, or upstream integration if the backend plus a short script offers comparable value.

Reconsider the product if users cannot supply real failures, labels and fixtures cost more than the findings are worth, or audits are useful once but do not become part of later work.

The next milestone is a reproduced false pass in a prospective user's existing suite, a corrected check that still accepts legitimate behavior, and reuse on their next change.
