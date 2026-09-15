# EDD Kit: prepare executable acceptance before implementation

EDD Kit turns feature intent into reviewed, executable acceptance criteria before production
implementation, then connects those criteria to development feedback and release evidence.

The initial audience is developers using coding agents to build LLM-powered features, in greenfield
or brownfield projects. An existing eval suite or historical escaped bug is not a prerequisite.

## The experience

**Prepare → Build → Check** in the developer's existing coding agent.

Prepare discovers relevant project context, clarifies consequential product decisions, records the
behavior specification, designs and generates the native evaluation pipeline, validates its graders,
and executes the available baseline. Generated code includes fixtures and adapters; production
feature implementation follows preparation. Work is scoped to the next meaningful behavior, not
an exhaustive specification of an entire product.

Build derives an implementation plan from the specification and baseline, then iterates application
changes with fast development evaluations. Check runs full acceptance and explains current evidence.
Deployment remains in the adopting project's existing workflow. Reviewed production findings feed
new regression cases and subsequent changes.

Grilling is a clarification technique, the specification describes intended behavior, the evaluation
pipeline makes acceptance executable, and the implementation plan describes the work to satisfy it.
These are complementary responsibilities, not competing workflow alternatives.

## Required pipeline

- A short human-readable behavior brief, contracts and stable requirement identities.
- Domain-specific cases, goldens/reference outcomes and provenance, with legitimate alternatives.
- Native DeepEval metric factories, deterministic checks where appropriate, and acceptance gates.
- Positive and negative controls mapped to the intended requirement; calibration and validation data
  have distinct roles. Generated labels require actual domain review.
- Fixtures, target adapters, observable output/state/action evidence, and reset per target trial.
- Development and acceptance profiles, bounded work/time, explicit credential references and cost
  visibility, plus reproducible dependency and evaluation identities.
- Honest baseline, per-observation reports, stale-evidence detection, and regression preservation.

## Evidence semantics

Criteria reviewed, pipeline executable, graders checked, baseline recorded, and candidate accepted
are different states. A failing application baseline can mean preparation succeeded. A broken
evaluator, missing observations or malformed output cannot support acceptance. A stub/reference
baseline is labeled honestly; unavailable application evidence never becomes an invented score.

Audit checks saved reviewed controls through the actual native graders. It does not establish that
live state collection is correct. Fixture/collector integration checks and application evaluations
provide different evidence. A success claim does not substitute for an actual state change.

Only complete, current PASS evidence satisfies the declared gate. Critical violations cannot be
averaged away; failures, infrastructure errors and insufficient evidence stay distinct. Direct
baseline comparison uses matching criteria and execution policy. Improvement and acceptance are
separate conclusions. Scenario counts, target trials and grader repetitions are reported separately.

## Product architecture and trust

Ship a local Python CLI/CI kit with DeepEval as the first backend and coding-agent skills for
generation. Native Python remains the authoring interface; no universal grader DSL or built-in LLM
authoring service is required. A default scaffold is a draft, not an automatically correct feature.

The first release targets reviewed cooperative code on Linux/macOS, single-turn LLM cases and
tool/state evidence through adapters. It does not promise hostile-code containment, protected hidden
datasets, a hosted approval service, conversational tracing, a new coding agent, or deployment control.
Local review records and hashes detect drift; they do not authenticate a human or prove chronology.
Normal repository review governs criteria and implementation in the same PR.

User-owned evaluation artifacts remain editable. Revisions show a semantic diff, preserve custom
work, invalidate affected evidence, and rerun the necessary checks. Kit upgrades preserve those
artifacts. Context and progress survive conversation resets through files and run records.

## Product validation

Test the complete experience on new and existing projects: time to first meaningful executable
baseline, manual repairs, unnecessary questions, review comprehension, reliable resumption, and
safe revision. Passing synthetic examples does not establish customer value or production coverage.

See [implementation requirements](docs/implementation.md), [workflow](docs/workflow.md), and
[authoring](docs/authoring.md). Historical [audit-first proposal](docs/idea-audit-first.md),
[initial draft](docs/idea-original.md), [evaluation](docs/evaluation.md), and [research](docs/research.md)
are retained for provenance; the current vision above supersedes their product-scope recommendations.
