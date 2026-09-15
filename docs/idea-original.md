**Yes, it makes sense—but “evals before code” is not new, and even the kit/skills packaging already has close precedents.** The opportunity is to make the practice substantially easier and more trustworthy, rather than introduce a new name for test-first development.

I would sharpen your idea to:

> **A kit that turns product intent into validated, executable acceptance criteria before a coding agent starts implementation—and requires evidence before declaring the feature done.**

The important addition is **validated**. Creating an eval is easy; creating an eval that rejects bad solutions and accepts genuinely good ones is the harder problem.

## 1. Is it something new?

### The methodology: no

Anthropic explicitly recommends defining planned capabilities through evals before an agent can fulfill them. There is also research on evaluation-driven agent development dating back to November 2024. So I would not position this as inventing eval-driven development. ([Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents "Demystifying evals for AI agents \ Anthropic"))

### The product: there is room, but it has close neighbors

These are the most relevant precedents I found:


| Existing project                                         | Overlap with your idea                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ECC’s** `eval-harness` **skill**                       | Explicitly defines expected behavior before implementation, with capability evals, regression evals, graders, and an evaluation workflow. ([GitHub](https://github.com/affaan-m/everything-claude-code/blob/main/skills/eval-harness/SKILL.md "ECC/skills/eval-harness/SKILL.md at main · affaan-m/ECC · GitHub"))                                                                                                                                                                                       |
| **GitHub Awesome Copilot’s** `eval-driven-dev` **skill** | Guides an agent through building an executable evaluation pipeline, producing scores, and analyzing results. ([GitHub](https://github.com/github/awesome-copilot/blob/main/skills/eval-driven-dev/SKILL.md "awesome-copilot/skills/eval-driven-dev/SKILL.md at main · github/awesome-copilot · GitHub"))                                                                                                                                                                                                 |
| **Spec Kit’s community Test-First Governance preset**    | Adds acceptance tests before implementation, requirement-to-test traceability, red/green evidence, and quality gates. ([GitHub](https://github.com/ka-zo/spec-kit-preset-test-first-governance "GitHub - ka-zo/spec-kit-preset-test-first-governance: Test-first governance preset for GitHub Spec Kit, providing coverage-complete TDD, BDD and ATDD, requirements traceability, professional test reporting, and risk-based quality gates for more reliable, high-quality implementations. · GitHub")) |
| **Promptfoo**                                            | Already provides much of the execution layer: declarative eval configuration, assertions, custom grading, and command-line/CI integration. ([GitHub](https://github.com/promptfoo/promptfoo "GitHub - promptfoo/promptfoo: Test your prompts, agents, and RAGs. Red teaming/pentesting/vulnerability scanning for AI. Compare performance of GPT, Claude, Gemini, DeepSeek, and more. Simple declarative configs with command line and CI/CD integration. Used by OpenAI and Anthropic. · GitHub"))      |
| **Consort**                                              | A September 9, 2026 preprint describes a spec-first framework with a deterministic orchestrator, human-approved gates, and immutable tests. Its claimed benefits are framed as a hypothesis, not an established result. ([arXiv](https://arxiv.org/abs/2609.09671 "[2609.09671] Introducing Consort: A Spec-First Agent Framework for Enforced, Test-Driven Development on Live Database Branches"))                                                                                                     |


These establish overlap; they do **not** establish that the whole problem is solved well.

My assessment: **a new methodology is a weak claim; a better integrated developer experience is a credible opportunity.** Even enforcement alone is not an untouched idea. Your differentiation needs to be specific and demonstrable.

## 2. First, distinguish two different products

There are two meanings of “eval-driven development,” and your architecture should not accidentally mix them.

**Developing an AI-powered product.** You are building a support agent, extraction pipeline, or research assistant. You evaluate the product’s behavior across scenarios, potentially with repeated trials and a mixture of programmatic and judgment-based grading.

**Developing ordinary software with a coding agent.** You are building an API, dashboard, or database migration. The implementation process involves AI, but the resulting software may be best evaluated with ordinary deterministic tests. An AI coding agent does not automatically make an LLM judge the right verification mechanism. Anthropic’s guidance makes this distinction too: coding-agent evaluation naturally uses executable tests, while open-ended outputs can require other graders. ([Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents "Demystifying evals for AI agents \ Anthropic"))

For the second category, the relationship to **acceptance-test-driven development** is very close. The existing Spec Kit preset explicitly covers stakeholder-facing acceptance evidence before implementation. ([GitHub](https://github.com/ka-zo/spec-kit-preset-test-first-governance "GitHub - ka-zo/spec-kit-preset-test-first-governance: Test-first governance preset for GitHub Spec Kit, providing coverage-complete TDD, BDD and ATDD, requirements traceability, professional test reporting, and risk-based quality gates for more reliable, high-quality implementations. · GitHub"))

**My suggested starting audience:** developers using coding agents to build **LLM-powered features**.

That gives you a concrete initial problem: how to combine product-quality evals, ordinary software tests, and the coding agent’s implementation loop. Keep the underlying format general, but do not initially promise “the development methodology for all software.”

## 3. Improve the central rule: “before implementation,” not “everything upfront”

I would change:

> “Create evals before the first line of code.”

to:

> **“Before implementing each meaningful behavior, define how success will be measured and verify that the evaluation can distinguish success from failure.”**

This avoids two traps.

First, an executable eval may itself require code: fixtures, graders, a test adapter, or a sandbox. That should be allowed before production implementation.

Second, you do not want to turn eval-first development into a giant upfront specification exercise. Start with one small behavior, then expand the suite as you learn.

My proposed loop is:

```text
Product intent
    → Eval contract
    → Cases + graders + environment
    → Validate the eval itself
    → Record baseline
    → Approve the contract
    → Implement → evaluate → revise
    → Independent release verification
```

### The central artifact: an eval contract

I would make the **eval contract**, rather than a large generated document, your central artifact.

It should answer:

**What behavior matters?** What inputs and initial conditions are in scope? What outcomes are acceptable? What must never happen? How will those outcomes be checked? What evidence is sufficient to proceed?

For example, imagine an order-cancellation assistant. An abridged format for your proposed kit could look like this:

```yaml
# Illustrative schema for your kit, not an existing tool's configuration.
version: 1
feature: order-cancellation

interface: contracts/support-agent.schema.json
cases: evals/order-cancellation/dev.jsonl

graders:
  task_outcome: graders/order_state.py
  authorization: graders/ownership.py
  communication: rubrics/confirmation.md

requirements:
  - id: cancel_correct_order
    grader: task_outcome

  - id: never_modify_another_users_order
    grader: authorization
    critical: true

  - id: explain_the_actual_result
    grader: communication

execution:
  reset_environment_per_trial: true
  development_trials_per_case: 3

release_policy: policies/order-cancellation.yaml
```

Notice that this specifies **observable behavior**, not the implementation.

It should not demand a particular class structure or tool-call sequence unless that is genuinely part of the requirement. A valid alternative solution should still pass.

Also, keep the short product spec. Evals give you concrete evidence, but they cannot enumerate every possible acceptable behavior. I would use:

> **Spec for intent; eval contract for acceptance; tests and eval runs for evidence.**

## 4. The strongest differentiator: evaluate the evals

This is where I would invest most of the product effort.

A weak kit does this:

```text
Generate 50 cases → implement → get 95% → celebrate
```

Your kit should first ask:

> **Could a bad implementation get that score?**

### Validate graders with known-good and known-bad examples

Before implementation, require examples that exercise the evaluation logic itself.

For the cancellation feature, I would include:


| Example behavior                                             | Expected grading result      |
| ------------------------------------------------------------ | ---------------------------- |
| Cancels the correct order and accurately explains the result | Pass                         |
| Says “cancelled” but changes nothing                         | Fail task outcome            |
| Cancels a different customer’s order                         | Fail authorization           |
| Correctly rejects an unauthorized cancellation               | Pass that rejection scenario |
| Uses different wording while preserving the correct meaning  | Still pass                   |


The second example is especially important: checking whether a response *claims* success is not equivalent to checking whether the requested state change occurred. Agent evaluation guidance explicitly distinguishes transcripts from actual environment outcomes. ([Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents "Demystifying evals for AI agents \ Anthropic"))

I would make a command such as `evalkit validate` produce feedback like this:

```text
Illustrative output:

Known-good examples accepted:  4/4
Known-bad examples rejected:   2/4

BLOCKED:
- A fabricated success message passed.
- A wrong-order cancellation passed.

The evaluation is not ready to guide implementation.
```

That is a more compelling demonstration than generating a large folder of tests.

### Add deliberate defects, not just more cases

Once a minimal implementation exists, introduce controlled defects: remove an authorization check, return a constant answer, skip a state change, or break an error path.

Then ask whether the suite catches them.

I would describe this as **testing the sensitivity of your acceptance criteria**, not proving that the suite is complete. No finite set of injected defects establishes complete coverage.

### Keep human judgment at the right boundary

The agent can draft cases and rubrics, but a domain owner should approve what “correct” means for important behaviors.

For model-based graders, include a small human-labeled calibration set and inspect both false passes and false failures. OpenAI’s guidance recommends calibration against human judgment and notes that model judges can exhibit position and verbosity biases. ([OpenAI Platform](https://platform.openai.com/docs/guides/evaluation-best-practices "Evaluation best practices | OpenAI API"))

**Separate “the grader runs” from “the grader is trustworthy.”** That distinction should appear throughout your user experience.

## 5. Make the workflow enforceable without pretending prompts are locks

A skill file saying “do not change the evals” is useful guidance. I would not treat it as a security boundary.

My design would distinguish two modes:

**Guided mode:** skills and local commands help an individual follow the process.

**Enforced mode:** a controlled runner and protected CI require approved evaluation artifacts and independently produced results.

The existing Spec Kit test-first preset acknowledges this same boundary: it cannot prevent contributors from bypassing its workflow and recommends required CI checks for mechanical enforcement. GitHub supports required status checks and review requirements through protected branches. ([GitHub](https://github.com/ka-zo/spec-kit-preset-test-first-governance "GitHub - ka-zo/spec-kit-preset-test-first-governance: Test-first governance preset for GitHub Spec Kit, providing coverage-complete TDD, BDD and ATDD, requirements traceability, professional test reporting, and risk-based quality gates for more reliable, high-quality implementations. · GitHub"))

For enforced mode, I would implement these boundaries:

**Before the build:** the orchestrator does not hand an implementation task to the coding agent until the contract, grader checks, and baseline are approved.

**During the build:** the agent can modify the application and add ordinary development tests, but cannot silently weaken approved acceptance criteria.

**Before merge:** a trusted evaluator checks the proposed application against the approved evaluation version. Changes to graders, thresholds, or datasets require explicit review and fresh evidence.

A hash is useful for identifying an evaluation version, but **a hash in a file that the same agent can rewrite is not an approval mechanism**. Anchor approval outside the mutable implementation workspace.

Similarly, hidden evaluation cases should not simply live in a directory named `hidden/` that the agent can read.

### Keep the criteria changeable—but changes explicit

Do not make evals permanently immutable. Sometimes the requirement or grader is wrong.

Instead, make an evaluation change a first-class event:

```text
Propose contract change
    → Explain why
    → Review the changed acceptance boundary
    → Revalidate graders
    → Establish a new baseline
```

That prevents both extremes: agents moving the goalposts to pass, and teams getting trapped by incorrect tests.

## 6. Treat uncertainty and failure modes as part of the product

I would give the kit four outcomes:

```text
PASS          Sufficient evidence for the declared gate
FAIL          Evidence violates the declared gate
INCONCLUSIVE  Insufficient or ambiguous evidence
ERROR         The evaluation did not execute correctly
```

This matters because an evaluation timeout, an empty dataset, or a broken grader must not accidentally become a successful run.

### Make the baseline meaningful

Before implementation, run against a stub, a simple baseline, or the current application.

Require evidence that the newly requested capability is missing or below target—not merely that an import crashed. Existing behavior should remain covered by regression checks.

Do **not** require every initial case to fail. A no-op baseline may correctly pass “must not modify unauthorized data.” And when the existing system already meets the requirement, the correct result may be “no implementation change needed.”

### Separate development feedback from release evidence

For my initial design, I would use three evaluation pools:

- **Development cases:** visible, fast, and used during iteration.
- **Held-out acceptance cases:** independent cases used sparingly for release decisions.
- **Production regressions:** reviewed cases derived from real failures after deployment.

Split related examples together. Putting one scenario in development and a lightly reworded version in acceptance gives a misleading impression of independence.

The need for realistic datasets, human review, and continuous addition of cases is consistent with current evaluation guidance. ([OpenAI Platform](https://platform.openai.com/docs/guides/evaluation-best-practices "Evaluation best practices | OpenAI API"))

### Avoid one aggregate “quality score”

For the cancellation example, I would report task success, authorization violations, communication quality, latency, and cost separately.

A high communication score must not compensate for canceling someone else’s order.

For stochastic behavior, record repeated trials, but distinguish **more attempts at the same task** from **more distinct task coverage**. A few development repetitions help expose instability; they do not certify high production reliability.

I would also report first-attempt success separately from success after retries. Otherwise the kit can reward an implementation that eventually succeeds while hiding its delay, cost, or unsafe intermediate actions.

## 7. How I would implement the kit

**Start with a small CLI plus coding-agent skills, not a new coding agent or a full evaluation platform.**

Spec Kit already has extension mechanisms and before/after command hooks, so a compatible extension is a plausible entry point. Keep your core independent so users do not need to adopt Spec Kit to use it. ([GitHub](https://github.com/github/spec-kit/blob/main/docs/reference/extensions.md "spec-kit/docs/reference/extensions.md at main · github/spec-kit · GitHub"))

### Keep the deterministic core small

I would put the following responsibilities in ordinary application code:

**Contract validation and lifecycle state.** Validate schemas, resolve referenced files, detect missing graders, track approvals, and decide which transitions are allowed.

**Evaluation adapters.** Invoke existing test/eval tools and normalize their output. Start with one ordinary test runner and one LLM evaluation backend. Promptfoo already supports programmatic and model-based assertions, so rebuilding those primitives would not be my first priority. ([Promptfoo](https://www.promptfoo.dev/docs/configuration/expected-outputs/ "Assertions and Metrics - LLM Output Validation | Promptfoo"))

**Evidence and gate evaluation.** Record the application commit, contract/dataset/grader versions, model identifiers and settings, environment fixtures, individual results, and gate decisions.

Keep the agent-facing skills responsible for proposing and explaining artifacts—not for being the final authority on whether a gate passed.

A useful internal result record would include:

```text
case_id, requirement_id, trial_id, grader_id,
status, score, evidence_reference, duration, error
```

You can aggregate that into either machine-readable output or a short review report.

### Design a small command surface

For example, these would be **proposed commands for your product**:

```bash
evalkit init
evalkit define order-cancellation
evalkit validate order-cancellation
evalkit baseline order-cancellation
evalkit approve order-cancellation
evalkit verify order-cancellation --candidate <commit>
```

An agent skill would guide the implementation loop between approval and verification, using development evaluations for feedback.

I would resist adding twenty commands. The user should mostly experience:

> Define what matters → check that the checks work → build → inspect evidence.

### Build the kit using its own principle

Your first acceptance cases should target the kit’s failure modes, before implementing its orchestrator.

For example: an unapproved contract blocks the build stage; changing a grader invalidates approval; zero executed cases cannot pass; a grader exception produces `ERROR`; an attempted threshold reduction requires review.

That gives you a credible demonstration of eval-first development **without needing a mature AI application first**.

## 8. What I would ship first—and how I would judge success

My initial release would contain just three things:

1. **One complete reference workflow**, such as a tool-using support assistant, with a good solution and deliberately bad solutions.
2. **The contract/validation/baseline/verification CLI**, one coding-agent integration, and one protected CI example.
3. **An evidence report** showing requirement coverage, grader calibration, baseline-to-candidate changes, and unresolved failures.

I would postpone dashboards, model leaderboards, a plugin marketplace, automatic prompt optimization, and an elaborate multi-agent architecture.

Then evaluate the kit itself against a serious baseline—not only against unstructured coding. Compare it with an existing spec-first/test-first workflow on the same representative tasks, with matched agent settings and comparable budgets.

The outcome measures I would choose are **time to an independently accepted feature, reviewer effort, missed defects, and evaluation-maintenance cost**. Do not use the pass rate on the kit’s own generated tests as the main proof that the kit works.

The central hypothesis to test is:

> **Does validating acceptance criteria before implementation reduce false confidence enough to justify the extra work?**

That is both a product question and an eval you can define before writing the kit.

---

**My recommendation:** build a **Spec Kit-compatible eval-contract kit**, with a standalone core, and make **grader validation plus independent acceptance evidence** its defining feature.

“Write evals before code” is the starting discipline. **“Show that the evals catch bad solutions before trusting the code” is the stronger product.**
