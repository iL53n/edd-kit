# Evaluator dependencies

Use EDD Kit 0.1.0 with native DeepEval 4.2.3 on a supported Python runtime. The
application and its ordinary tests use only the Python standard library. No
provider credentials or network calls are needed.

Use the hashed evaluator lock distributed with the installed EDD package at
`assets/requirements-eval.lock`; do not maintain a second copy in this example.
In the source repository it is `src/edd_kit/assets/requirements-eval.lock`.
Install those dependencies with `pip install --require-hashes -r PATH_TO_LOCK`,
then install the EDD wheel separately. Extend a project's dependency lock and
declare it as a contract artifact when adapting this example with extra evaluator
dependencies. EDD records the actual installed evaluator runtime identity.

The example's target commands use `python3` from PATH. Run in the intended
environment; evidence captures the resolved executable identity. Re-run audit,
baseline and acceptance when dependencies or runtime change. This portable source
example intentionally contains no developer-specific runtime dump, generated review packet, or
review decision log.
