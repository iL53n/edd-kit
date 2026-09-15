# Evaluator dependencies

Use the EDD package's `assets/requirements-eval.lock` for hashed DeepEval 4.2.3
dependencies and install the EDD wheel separately. In this repository the lock is
`src/edd_kit/assets/requirements-eval.lock`; it is intentionally not duplicated
in the example. The existing application uses only the Python standard library.

The `current` target uses `python3` from PATH. Run inside the intended environment
and obtain fresh evidence after adapting interpreter/dependency configuration.
Both profiles have one target trial, one grader repetition and zero grader cost.
The actual evaluator runtime is recorded by EDD; no provider access is required.
