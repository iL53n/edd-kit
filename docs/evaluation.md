# Evaluation of the EDD Kit idea

Reviewed 2026-09-15. This is a product and technical assessment, supported by primary-source research. It is not a customer study, implementation benchmark, or DeepEval test run.

## Verdict

The idea merits a small practical experiment. The current evidence does not justify a broad platform or a claim to a new methodology.

Its best insight survives scrutiny: a passing test is useful only to the extent that its acceptance criteria represent the intended behavior. Checking those criteria against relevant good and bad examples can expose false confidence.

Its weakest assumption is commercial: that this practice requires a separate product. Existing evaluation tools already provide much of the mechanism. The remaining question is whether EDD Kit makes a recurring task sufficiently easier to earn adoption.

The revised [proposal](../idea.md) preserves acceptance criteria before implementation, while making an audit of an existing suite the entry point. The [original](idea-original.md) and [source audit](research.md) remain available.

## Assessment by dimension

| Dimension | Assessment | Evidence needed next |
| --- | --- | --- |
| Problem mechanism | Credible: a grader can accept an incorrect outcome or reject a valid one | A prospective user's reproducible example |
| Methodological novelty | Low | No further novelty claim is necessary |
| Standalone differentiation | Unproven, with substantial documented overlap | Comparison against the same backend plus its calibration workflow |
| Local audit feasibility | Plausible with narrow inputs and one adapter | Replay the actual grader without duplicating its configuration |
| General enforcement feasibility | Substantially larger than the suggested CLI | A concrete trust boundary and isolation design |
| Adoption | Unproven; fixtures and labels may dominate cost | Observe onboarding and repeat use |
| Commercial potential | Unknown | A scoped paid commitment, distinct from enthusiasm |
| Evaluation quality | Strong initial principles, incomplete operational definitions | Grader-specific controls, execution accounting, comparable versions |

These are judgments about the document, not numerical scores disguised as market measurements.

## 1. The competitive correction is material

The original says that evaluating the evaluations is the strongest differentiator. That is a useful design priority, but the research does not support it as a distinctive capability.

Promptfoo documents calibration against labeled outputs, holdout validation, and drift monitoring. DeepEval provides an agent workflow; Confident AI documents metric alignment with human review. [Promptfoo judge guide](https://www.promptfoo.dev/docs/guides/llm-as-a-judge/), [DeepEval agent workflow](https://deepeval.com/docs/vibe-coding), [Confident AI human review](https://www.confident-ai.com/blog/human-in-the-loop-ai-agent-evaluation).

The hardest competitor is therefore an existing runner, several well-chosen controls, and a small script. A kit must beat that combination on something a user experiences: setup effort, missed defects, review time, or maintenance.

A unified report may be valuable. A new manifest may instead become duplicate configuration. The pilot should test both possibilities before introducing an extensible contract language.

This changes the recommendation from “build the differentiated kit” to “test whether the integrated task warrants a kit.”

## 2. Improve sequencing without abandoning eval-first

The original audience is defined by two technologies: coding agents and LLM features. That does not explain who urgently needs help.

A sharper user is the owner of an existing feature whose current suite accepted a known incorrect behavior. Their next change supplies a concrete reason to act.

Starting with an existing suite removes one adoption dependency. The user can inspect a real failure, repair a check, and decide whether the method helps. After that, defining controls before implementing the next behavior is a natural extension of the original idea.

This is an entry strategy, not evidence that preimplementation acceptance work lacks value. Greenfield work still fits when a reference fixture can expose the intended success and failure states.

There is a limit: a team without an executable harness, accessible evidence, or a person who can judge correctness may need consulting or basic test setup. Calling that work a one-command onboarding experience would hide the main cost.

## 3. The evaluation can share the implementation's blind spot

Generating the spec, cases, implementation, and judge with one agent can reproduce the same misunderstanding throughout the chain. A second agent does not automatically provide an independent interpretation.

More examples do not necessarily help. Fifty paraphrases of the same happy path may contribute less than one reviewed counterexample.

The quality check needs three questions:

1. Is the expected outcome itself justified by the product requirement?
2. Does the intended grader detect that distinction?
3. Does the live harness provide the evidence the grader needs?

For each negative control, store the expected failure per requirement or grader. A wrong-order cancellation that fails only because the response is empty has not tested the authorization criterion.

Include acceptable alternatives as positive controls. Otherwise a stricter grader can appear improved simply because it rejects everything.

Disputed domain labels remain unresolved until reviewed. Improving agreement with an incorrect label does not improve the product.

## 4. Saved examples and live behavior establish different things

Saved output replay is an inexpensive way to find grader mistakes. It can run before the application exists. It cannot establish that a real state change occurred or that state collection works.

The cancellation example needs a fixture-owned order store and, for requirements about forbidden actions, a record of side effects. Final state alone can miss an unauthorized modification that was subsequently reversed.

Use deliberately defective variants only when their defect can be exercised. A variant that fails to import is not a successful authorization challenge. A mutation that changes no relevant behavior should not inflate a defect-detection score.

This is why the revised MVP includes one fixed harness demonstration but postpones general mutation and sandbox infrastructure. The general integration cost is a separate feasibility question.

## 5. The enforcement promise concealed another product

The original combines local commands with externally anchored approval, implementation dispatch control, hidden cases, protected CI, and trusted release verification.

A local CLI can detect drift and guide cooperative users. It cannot prevent other code from being written, edited, or executed. That limitation does not invalidate the local product.

Enforcement requires separating the authority to change application code from the authority to define criteria and publish acceptance results. Candidate code must not receive evaluator credentials or run alongside secret evaluation assets.

GitHub's documentation warns about privileged workflows executing untrusted pull-request code. A protected workflow name or a hash file is not a substitute for that execution boundary. [GitHub secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use).

Accordingly, the revised version defers enforced infrastructure. Imported or locally generated evidence remains useful for review, with its trust level stated explicitly.

## 6. “Pass” needs a precise meaning

The original four outcomes are a good starting point. They require aggregation and execution rules to avoid accidental success.

A control audit and an application run invert one important expectation: rejecting a known bad control is a successful audit observation. Keep those levels separate.

Preserve both the decision and execution health. A valid critical violation establishes FAIL even if another case later errors; those errors still need to be visible. Noncritical failures follow the declared threshold rather than automatically failing the whole run. Missing cases, judge exceptions, unsupported result formats, and empty data must never disappear from the denominator.

Candidate acceptance must require a passing control audit for the same evaluation bundle. It is separate from improvement over the baseline: getting better does not necessarily meet the requirement, and an intentionally weak baseline must not fail a satisfactory candidate.

A product exceeding its specified response deadline is an application failure. The evaluation service losing its connection is an execution problem. Treating both as the same failure can send implementation work in the wrong direction.

Record all inputs that influence the decision. Separate application prompts and models from evaluator settings, even when they share a native configuration file. A changed policy, fixture, evaluator dependency, or grader creates a new evaluation version. Reevaluate baseline and candidate under the same evaluation bundle before attributing a score difference to the target change.

Version identifiers improve traceability. Mutable remote models and services still limit exact reproducibility.

## 7. Statistical confidence must match the evidence

The original correctly warns against a single aggregate quality score and against treating repetitions as new scenario coverage. The product should make those warnings operational.

Use distinct counts for scenarios, application trials, grader repetitions, product retries, and evaluator retries. Report observed failures even if a later retry succeeds. Record whether results came from a cache.

Small runs can diagnose specific failures. They cannot establish broad reliability. As an illustration derived from the binomial model, zero failures in 100 independent trials still gives a one-sided 95% upper failure-probability bound of approximately 2.95%:

```text
upper bound = 1 - 0.05^(1 / 100)
```

That calculation assumes independent trials with the same failure probability and a fixed sample plan. Repeated examples and heterogeneous scenarios may violate those assumptions. Do not turn the illustration into a default release policy.

Keep calibration and validation samples separate. A held-out example used to tune the rubric has become development data, even if its file still says “holdout.”

## 8. The business bottleneck may be human preparation

The likely cost is not generating a YAML file. It is locating realistic evidence, resolving what “correct” means, constructing fixtures, and maintaining them as the product changes.

A useful economic hypothesis is:

```text
Value per change =
  review effort saved
  + value of useful defects caught
  - recurring labeling, execution, and maintenance cost

Adoption also has to repay initial integration work.
```

This is a framework for measurement, not a calculated return on investment. Defect value should not be filled with invented production-loss estimates.

If users need one intensive audit and then their native runner is sufficient, the outcome could be a service, template, or upstream contribution. If they repeatedly need shared reviewed cases and maintained verification, a larger product may be justified.

The kit does not acquire a defensible advantage merely by accumulating generated tests. Reusable integrations, consented domain knowledge, and lower maintenance could matter if actual users demonstrate their value.

## 9. Validate the smallest uncertain claim first

First run the audit manually using an existing backend. Capture a reproducible false pass, repair the check, verify legitimate behavior remains accepted, and observe reuse.

Then compare the kit against the same backend, same labels, and same reviewer attention. This controls for the possibility that any improvement comes from spending more time thinking about requirements.

For a later efficacy study, include an ablation: the same acceptance-first process with and without explicit control validation. Otherwise the study cannot isolate the proposed addition.

Preselect independently judged acceptance cases, balance task difficulty, record total budgets, and retain incomplete tasks. Use separate matched tasks or fresh participants where repeating a task would introduce learning effects. Report individual failures and uncertainty as well as averages.

Do not use pass rates on the kit's own generated cases as its primary success measure.

## 10. What changed in the proposal

| Original emphasis | Revised decision | Why |
| --- | --- | --- |
| “Evaluate the evals” as differentiation | Treat it as an existing practice; test incremental workflow value | Competitive overlap is substantial |
| Broad category of developers | Engineer with an existing suite and a known missed failure | Makes the problem and trigger observable |
| Adopt the full process first | Audit an existing check, then use controls before the next change | Reduces initial adoption dependencies |
| Multiple adapters and enforcement in the MVP | One backend, local audit, comparison, one demo | Keeps the feasibility experiment bounded |
| “Validated eval” | Describe which checks passed and their evidence limits | Avoids implying completeness |
| Approval and hidden-case infrastructure | Defer until a recurring need warrants it | Local usefulness can be established earlier |
| Broad benchmark as the first proof | Manual pilot, repeat use, then controlled comparison | Tests demand before platform investment |

## Final recommendation

Proceed with the manual pilot and a small integration if the pilot succeeds. Preserve the eval-before-implementation principle as the workflow, and make the product prove its value against existing tools.

The most informative next result is a real team's corrected acceptance check that they reuse on a subsequent change. It would establish more than another generated suite, methodology document, or synthetic score.
