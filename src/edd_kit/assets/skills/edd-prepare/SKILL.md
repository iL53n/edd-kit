---
name: edd-prepare
description: Turn an LLM feature idea into a small, executable EDD measurement bundle before or during implementation.
---

# Prepare a behavior measurement

Create enough shared context to measure the feature with native DeepEval metrics. Keep the
specification short and treat it as a living hypothesis rather than a complete design.

## 1. Recover the intent

Read the repository instructions, relevant product material, nearby application code, and [the authoring reference](references/authoring.md). Reuse an existing specification by reference when possible.

Write down:

- the user-visible behavior;
- the important failures or harms;
- the target that can be executed now;
- facts, assumptions, and unresolved decisions.

Ask about decisions that would materially change correctness. Continue with independent preparation while they are unresolved.

## 2. Create the initial bundle

For a new change, run:

```bash
edd prepare CHANGE --brief TEXT --template starter
```

Replace the scaffold with a small domain-specific bundle:

- stable requirement IDs;
- representative cases with expected behavior;
- a metric factory for every mapped requirement;
- the smallest target adapter and fixtures needed to execute the cases;
- source and expectation provenance for every case.

Start with roughly 10–20 diverse cases when the domain supports them. This is an orientation, not a gate. Prefer real traces and reviewed examples, then add synthetic boundary and adversarial cases. Mark cases as deferred when their expected behavior is still unknown; do not invent a golden answer.

Controls and formal approval records are optional for ordinary measurement. Add them when the user needs strict acceptance evidence.

## 3. Validate and measure the starting point

Run `edd inspect CHANGE --json` and fix configuration or mapping errors. If an executable current target or explicit stub exists, record the starting behavior:

```bash
edd measure CHANGE --target TARGET --stage baseline --profile dev
```

A failing behavior decision is still a successful measurement when execution completed. Broken imports, missing evidence, and provider errors are execution problems and must stay visible.

Run `edd status CHANGE` and hand off the report, known gaps, and next useful action. Continue with [edd-build](../edd-build/SKILL.md) when implementation is in scope.

## Strict acceptance branch

When the user explicitly needs a release gate, compliance evidence, or reviewer sign-off, follow [the strict acceptance workflow](references/acceptance.md). Do not impose that ceremony on exploratory development.
