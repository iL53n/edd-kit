# EDD Kit Domain Language

## Intent

A short, revisable description of the user-visible behavior and important risks.

## Requirement

A stable, human-readable behavior that a measurement evaluates.

## Case

A concrete scenario with source provenance, an expected behavior, and one or more mapped
requirements.

## Deferred case

A visible scenario whose expected behavior is unresolved. It is not executed or graded until the
expectation is supplied.

## Evaluation bundle

The versioned requirements, cases, metrics, fixtures, dependencies, and execution policy that define
a measurement instrument.

## Measurement

Recorded observations from running a specific target against an evaluation bundle and profile.

## Execution status

Whether a measurement completed, is inconclusive, or failed to produce trustworthy observations.

## Behavior decision

The configured metrics' conclusion about observed behavior. It remains separate from execution
status.

## Comparison

A case-level and requirement-level view of two measurements. Numeric deltas require the same
evaluation bundle and profile.

## Control

A labelled worked example used to test whether a grader accepts or rejects a known outcome. Controls
are optional for development measurements and required by strict acceptance.

## Strict acceptance

An optional gate supported by current domain review, technical validation, grader audit, and
candidate execution evidence for the same identities.
