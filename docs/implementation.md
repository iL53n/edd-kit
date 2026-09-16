# Implementation contract

EDD Kit is a local Python CLI plus coding-agent skills for measuring LLM feature behavior during
development. DeepEval is the first grading backend. The default workflow is lightweight; the
existing formal acceptance workflow remains available when explicitly needed.

## Required deliverables

1. Installable `edd` CLI, reproducible DeepEval 4.2.3 evaluator dependencies, and Codex/Claude
   skills as the primary authoring experience.
2. A short intent, stable requirements, native cases and metric factories, target adapters, and
   bounded development and acceptance profiles.
3. Case provenance for both input and expected behavior, plus deferred cases that remain visible
   without receiving a pass/fail decision.
4. `edd measure` for execution, durable run records, default Markdown/JSON reports, and separate
   execution status and behavior decision.
5. `edd compare` and `--compare-to` for saved runs. Numeric deltas require matching evaluation
   bundles and profiles; incompatible runs show the reason and case-set diff.
6. Default `edd status` guidance for prepare, measure, and improve. Strict readiness remains
   available through `edd status --acceptance`.
7. Optional formal acceptance with reviewed controls, domain and technical decisions, audit,
   acceptance-profile execution, verification, consolidated reports, and CI.
8. Bounded process execution, explicit credential references, no implicit dotenv/telemetry/cloud
   upload, durable evidence identities, fault tests, packaging smoke, and documented trust limits.

## Public seams

The public seams are CLI outcomes, the `Case`/`Control`/`Suite` Python interface, native
DeepEval metrics, the target JSON process protocol, run/report records, installed skills, and
scaffold functions.

A completed development measurement returns success even when its behavior decision is `FAIL`.
Execution errors return 2 and inconclusive evidence returns 3. Strict `run`, `check`, and
`verify` retain their acceptance-oriented exit behavior.

Saved records are interpreted using their saved requirements. Later edits do not rewrite historical
decisions. Changes to cases, metrics, fixtures, dependencies, or policy produce a new bundle
identity and disable direct numeric comparison with older bundles.

## Ownership and scope

`evals/<change>/` contains user-owned intent and evaluation code. `targets/<change>/` contains
independently changing application adapters. `.edd/` contains local runs and generated reports.

The coding agent proposes scenarios and evolves them in small batches. The CLI does not invent
domain expectations. Humans remain responsible for consequential labels and may add formal review
when risk requires it.

The first scope covers cooperative reviewed code on Linux/macOS, single-turn LLM cases, and
tool/state evidence through adapters. EDD does not provide hostile-code isolation, authenticated
review, hidden datasets, a hosted approval service, or deployment authorization.

## Completion evidence

The [verification record](verification.md) maps these requirements to tests and executable smoke
flows. The [usability protocol](usability.md) tests whether the lighter workflow helps real teams
find useful gaps without excessive specification work.
