# Evaluation dependencies

The generated suite uses native DeepEval metrics and the installed EDD Kit SDK.
Use the same environment and locked EDD Kit dependencies that provide `edd`.
Project initialization does not install packages or make network requests.

Before approving a release contract, list the relative paths of the project lock
files governing evaluation dependencies in `contract.json` under `artifacts`.
Only include evaluator dependencies there. Application target files are declared
separately under `targets` so application changes do not alter acceptance criteria.

This deterministic example needs no provider key or Confident AI account.
It is an example of wiring, not an evaluation of your feature's quality.
