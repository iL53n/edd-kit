# Engineer–domain-owner pilot protocol

Run this protocol with at least two independent pairs on real LLM-backed features. The goal is to
test whether EDD improves development decisions without requiring a complete specification.

## Tasks

1. The engineer gives the coding agent an existing feature request and relevant repository context.
2. The agent creates a short intent and roughly 10–20 initial scenarios, clearly marking synthetic,
   trace-derived, reviewed, and deferred expectations.
3. The pair reviews only consequential or uncertain expectations, then measures the current target.
4. The engineer implements one small slice and measures the candidate against the baseline.
5. The pair inspects failures and adds no more than five focused scenarios for one newly discovered
   failure class.
6. After the bundle changes, the engineer explains why the old numeric delta is unavailable and
   reruns both application versions when a direct comparison is useful.
7. For one high-risk feature, the pair also tries the optional strict acceptance branch.

## Record

- Time to the first executable measurement.
- Number and duration of human questions before the first run.
- Scenarios removed, corrected, deferred, or added after observing the application.
- Important behavior gaps found before merge.
- Whether users distinguish execution status from behavior decision.
- Whether users understand why two runs are or are not numerically comparable.
- Agent iterations that make no useful progress.
- Whether the team voluntarily uses EDD on a second eligible feature.

## Product signals

The workflow is promising when both pairs reach a useful first measurement quickly, discover at
least one decision-relevant gap, and can explain the report without reading evaluator code.

The workflow needs simplification when users spend more time perfecting the initial specification
than learning from measurements, accept synthetic expectations without review, or treat a score as
production reliability.

Failure to meet a signal is a product finding. Revise the skill instructions, reports, or defaults
and repeat the affected task.
