# Contributing to EDD Kit

EDD generates executable acceptance criteria before feature implementation. Preserve that workflow for both new and existing applications; the cancellation example is one demonstration, not the only supported domain.

## Development environment

Use Python 3.11, 3.12, or 3.13 on Linux or macOS. Install a uv version compatible with the committed lockfile; the CI installer reads its uv version from `uv.lock`.

```bash
uv sync --locked --group dev
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export DEEPEVAL_TELEMETRY_OPT_OUT=YES
export DEEPEVAL_DISABLE_DOTENV=1
uv run --no-sync ruff check src tests scripts
uv run --no-sync ruff format --check src tests scripts
uv run --no-sync mypy src/edd_kit
uv run --no-sync python -m pytest
```

The default tests use synthetic data and require no model-provider credentials. Pytest plugin autoload is disabled so installed SDK plugins cannot silently change the test environment. If a test requires an optional plugin, declare and load it explicitly.

For a dependency change, update `pyproject.toml` and `uv.lock` together, explain the compatibility impact, and rerun the affected checks. DeepEval's supported version is intentional: upgrading it requires native-metric compatibility and generated-workflow validation, not just a changed version constraint.

## Changes and tests

Keep changes focused on observable behavior. For a feature or bug fix, add a failing test at the relevant public seam, implement the behavior, and run the checks appropriate to the change. Useful seams include CLI outcomes, native metric handling, complete evidence accounting, the target protocol, and installed-package resources.

Exercise both legitimate behavior and relevant defects. A test that only checks that a Markdown heading exists does not demonstrate that an agent skill generates a working pipeline. For skill changes, use a bounded example in a temporary project and inspect the generated artifacts and evaluation results. Include a non-cancellation feature when the change affects general generation behavior.

Preserve user-authored files and existing manual changes. Contract revisions should explain their effect on acceptance, controls, review, and comparable baseline evidence. Keep actual acceptance decisions separate from baseline improvement and execution health.

## Pull requests

Describe the concrete problem, resulting behavior, and validation. Include limitations that affect the conclusion. A PR may contain criteria and implementation together; reviewers should read the committed `REVIEW.md`, domain decisions, control provenance, grader audit, and technical decisions before the implementation diff. A criteria correction must create a new digest and explicit review decision rather than overwrite an approved expectation invisibly.

Do not include credentials, production conversations, private fixtures, or raw local `.edd/` history. Follow [SECURITY.md](SECURITY.md) for vulnerability reports and trust boundaries.

## Distribution checks

Build with the locked build dependencies already installed in the development environment:

```bash
uv run --no-sync python -m build --no-isolation
uv run --no-sync python -m twine check --strict dist/*
```

The [CI workflow](.github/workflows/ci.yml) also installs the wheel as an isolated uv tool and over
the editable checkout, then exercises packaged skills, templates, and CLI scaffolding from temporary
directories. Its required check succeeds only when lint, types, all six operating-system/Python test
combinations, and all distribution smoke tests succeed.

The [release-artifact workflow](.github/workflows/release.yml) runs the same checks when manually dispatched for a selected revision. Download and inspect its wheel and source distribution before any separately authorized publication. A successful local run does not establish that the hosted matrix has run.

## Publishing to PyPI

`uv tool install edd-kit` resolves the package from PyPI. Before the first release, configure a
PyPI pending trusted publisher for project `edd-kit` with GitHub owner `iL53n`, repository
`edd-kit`, workflow `publish.yml`, and environment `pypi`. Create a matching protected `pypi`
environment in the GitHub repository. No long-lived PyPI token is required.

After the release artifact and version have been reviewed, create and push an annotated version
tag that exactly matches `pyproject.toml`:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

The tag-triggered [publish workflow](.github/workflows/publish.yml) reruns the full CI matrix, checks
that the tag matches the package version, builds and smoke-tests the distributions in an isolated
uv tool environment, and publishes from a separate least-privilege job using PyPI trusted
publishing. Do not reuse a version already uploaded to PyPI; increment the project version and lock
before tagging the next release.

Action updates should retain full commit pins and verify each revision against the upstream release. Current pins were resolved from [checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-uv v10.1.0](https://github.com/astral-sh/setup-uv/releases/tag/v10.1.0), and [upload-artifact v7.0.1](https://github.com/actions/upload-artifact/releases/tag/v7.0.1).
