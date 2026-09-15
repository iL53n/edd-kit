# Evaluation dependencies

Use the installed EDD Kit environment with its native DeepEval dependency.
This synthetic reference needs no provider key, network access, or Confident AI account.
Initialization installs no dependencies.

The suite uses deterministic DeepEval metrics. `candidate` is an offline toy
application, not an LLM agent. `stub` lacks the capability; `noop` claims success
without changing state; `wrong-owner` deliberately omits authorization.

When adapting this workflow, list the evaluation dependency lock files in the
contract's `artifacts`. Keep target implementations under `targets` so replacing
application code cannot accidentally replace acceptance criteria.
