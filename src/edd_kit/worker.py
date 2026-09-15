"""Private evaluator process: native suite loading, planning, and observation streaming.

This is an isolation boundary for cooperative code, not a hostile-code sandbox.
Application modules never enter this interpreter through the target protocol.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.metadata
import importlib.util
import json
import math
import os
import re
import signal
import sys
import time
import weakref
from pathlib import Path
from typing import Any, Literal

# Importing this module configures DeepEval before any user suite can import it.
from .backend import SUPPORTED_DEEPEVAL_VERSION, grade
from .project import Project, ProjectError, safe_path
from .suite import Case, Control, Suite
from .target import TargetError, invoke_target


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value))


def _json_value(value: object) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise ProjectError("Suite fixtures and metadata must contain finite JSON values") from None


def _check_imports(project: Project) -> None:
    """Detect undeclared local evaluator imports, including imports made lazily."""
    permitted = [project.directory]
    permitted.extend(safe_path(project.root, item) for item in project.contract.artifacts)
    framework = Path(__file__).resolve().parent
    interpreter = Path(sys.prefix).resolve()
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not isinstance(filename, str):
            continue
        path = Path(filename).resolve()
        if not path.is_relative_to(project.root):
            continue
        if path.is_relative_to(framework) or path.is_relative_to(interpreter):
            continue
        if not any(
            path == allowed or (allowed.is_dir() and path.is_relative_to(allowed))
            for allowed in permitted
        ):
            raise ProjectError("Evaluator imported project code outside the declared bundle")


def _metric_info(factory, *, require_fresh: bool = True) -> dict:
    from deepeval.metrics import BaseMetric

    if not callable(factory):
        raise ProjectError("Every requirement needs a callable metric factory")
    try:
        metric = factory()
        comparison = factory() if require_fresh else None
    except Exception:
        raise ProjectError("Metric factory construction failed") from None
    if require_fresh and metric is comparison:
        raise ProjectError("Metric factories must return a fresh instance for each observation")
    if not isinstance(metric, BaseMetric) or metric.flaky or metric.requires_trace:
        raise ProjectError(
            "Only non-flaky, non-trace single-turn BaseMetric factories are supported"
        )
    threshold = metric.threshold
    if (
        threshold is None
        or type(threshold) not in (int, float)
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 1
    ):
        raise ProjectError("Gating metrics require a finite threshold between zero and one")
    model = getattr(metric, "evaluation_model", None)
    requires_paid = model is not None or getattr(metric, "model", None) is not None
    info = {
        "metric_class": f"{type(metric).__module__}.{type(metric).__qualname__}",
        "threshold": float(threshold),
        "requires_paid": requires_paid,
        "evaluation_model": model if isinstance(model, str) else None,
    }
    # Freeze reviewable GEval reasoning steps; generating these on first grade would
    # change the evaluator after review and use unplanned provider calls.
    if type(metric).__module__.startswith("deepeval.metrics.g_eval"):
        steps = getattr(metric, "evaluation_steps", None)
        if not steps:
            raise ProjectError("GEval requires explicit reviewed evaluation_steps")
    for name in ("evaluation_steps", "criteria", "strict_mode", "include_reason"):
        value = getattr(metric, name, None)
        if value is not None:
            _json_value(value)
            info[name] = value
    return info


def _load(project: Project) -> tuple[Suite, dict]:
    if importlib.metadata.version("deepeval") != SUPPORTED_DEEPEVAL_VERSION:
        raise ProjectError("DeepEval 4.2.3 is required")
    from deepeval.test_case import LLMTestCase

    sys.path.insert(0, str(project.directory))
    spec = importlib.util.spec_from_file_location("_edd_evaluation_suite", project.suite_path)
    if spec is None or spec.loader is None:
        raise ProjectError("Cannot load the configured suite entrypoint")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        raise ProjectError("Evaluator suite import failed") from None
    builder = getattr(module, project.entrypoint, None)
    if not callable(builder):
        raise ProjectError("Configured suite entrypoint is not callable")
    try:
        suite = builder()
    except Exception:
        raise ProjectError("Evaluator suite construction failed") from None
    if (
        not isinstance(suite, Suite)
        or not isinstance(suite.cases, list)
        or not isinstance(suite.controls, list)
        or not isinstance(suite.metrics, dict)
    ):
        raise ProjectError("Entrypoint must return an edd_kit.Suite")
    requirements = {requirement.id for requirement in project.contract.requirements}
    if set(suite.metrics) != requirements:
        raise ProjectError("Metric factory keys must exactly match contract requirements")
    ids = set()
    for case in suite.cases:
        if not isinstance(case, Case) or not _identifier(case.case_id) or case.case_id in ids:
            raise ProjectError("Cases require unique stable IDs")
        ids.add(case.case_id)
        if (
            not isinstance(case.test_case, LLMTestCase)
            or case.test_case.multimodal
            or case.test_case.actual_output is not None
        ):
            raise ProjectError(
                "Application cases need text LLMTestCase without saved actual_output"
            )
        if case.test_case.flaky or any(
            getattr(case.test_case, field) is not None
            for field in (
                "retrieval_context",
                "tools_called",
                "completion_time",
                "token_cost",
                "input_token_count",
                "output_token_count",
                "mcp_tools_called",
                "mcp_resources_called",
                "mcp_prompts_called",
            )
        ):
            raise ProjectError(
                "Application cases cannot contain saved observed fields or flaky mode"
            )
        if (
            not isinstance(case.requirements, tuple)
            or not case.requirements
            or len(set(case.requirements)) != len(case.requirements)
            or not set(case.requirements).issubset(requirements)
        ):
            raise ProjectError("Case requirements must be unique declared requirement IDs")
        if (
            not isinstance(case.profiles, tuple)
            or not case.profiles
            or len(set(case.profiles)) != len(case.profiles)
            or not set(case.profiles).issubset(project.contract.profiles)
        ):
            raise ProjectError("Case profiles must be unique configured profile names")
        if not isinstance(case.fixture, dict):
            raise ProjectError("Case fixture must be a JSON object")
        if any(
            not isinstance(value, str) for value in (case.description, case.expected_behavior)
        ) or any(
            not isinstance(values, tuple)
            or any(not isinstance(value, str) or not value.strip() for value in values)
            for values in (case.acceptable_alternatives, case.unacceptable_behaviors)
        ):
            raise ProjectError("Case review descriptions must be text")
        _json_value(case.fixture)
        _json_value(case.test_case.metadata)
    case_ids = set(ids)
    for control in suite.controls:
        if (
            not isinstance(control, Control)
            or not _identifier(control.control_id)
            or control.control_id in ids
        ):
            raise ProjectError("Controls require unique IDs distinct from application cases")
        ids.add(control.control_id)
        if (
            not isinstance(control.test_case, LLMTestCase)
            or control.test_case.multimodal
            or control.test_case.flaky
            or not isinstance(control.test_case.actual_output, str)
        ):
            raise ProjectError("Controls need text LLMTestCase with a saved actual_output")
        if (
            control.requirement_id not in requirements
            or type(control.expected_pass) is not bool
            or not isinstance(control.source, str)
            or not control.source.strip()
            or control.partition not in {"calibration", "validation"}
            or (
                control.reviewed_by is not None
                and (not isinstance(control.reviewed_by, str) or not control.reviewed_by.strip())
            )
            or (
                control.case_id is not None
                and (not _identifier(control.case_id) or control.case_id not in case_ids)
            )
            or not isinstance(control.rationale, str)
            or not isinstance(control.contributed_by, str)
            or type(control.independent) is not bool
        ):
            raise ProjectError("Control labels, source, partition, and review must be valid")
        _json_value(control.test_case.metadata)
    metrics = {name: _metric_info(factory) for name, factory in suite.metrics.items()}
    _check_imports(project)
    return suite, metrics


def _plan(
    project: Project,
    suite: Suite,
    metrics: dict,
    operation: str,
    profile: Literal["dev", "acceptance"],
) -> dict:
    config = project.contract.profiles[profile]
    control_gaps = []
    application_gaps = []
    review_gaps = []
    for requirement in project.contract.requirements:
        matching = [
            control
            for control in suite.controls
            if (control.requirement_id == requirement.id and control.partition == "validation")
        ]
        for outcome, label in ((True, "positive"), (False, "negative")):
            if not any(control.expected_pass is outcome for control in matching):
                control_gaps.append(f"{requirement.id}: missing {label} validation control")
        for control in matching:
            if not control.rationale.strip() or not control.contributed_by.strip():
                control_gaps.append(
                    f"{control.control_id}: validation control provenance is incomplete"
                )
        if not any(not control.expected_pass and control.independent for control in matching):
            control_gaps.append(
                f"{requirement.id}: missing independently authored negative validation control"
            )
        coverage = sum(
            profile in case.profiles and requirement.id in case.requirements for case in suite.cases
        )
        if coverage < requirement.min_cases:
            application_gaps.append(
                f"{requirement.id}: insufficient distinct application cases for {profile}"
            )
    for case in suite.cases:
        if not case.description.strip() or not case.expected_behavior.strip():
            review_gaps.append(f"{case.case_id}: specialist review description is incomplete")
    cases = [
        {
            "case_id": case.case_id,
            "requirements": list(case.requirements),
            "profiles": list(case.profiles),
            "input": case.test_case.input,
            "reference_output": case.test_case.expected_output,
            "description": case.description,
            "expected_behavior": case.expected_behavior,
            "acceptable_alternatives": list(case.acceptable_alternatives),
            "unacceptable_behaviors": list(case.unacceptable_behaviors),
        }
        for case in suite.cases
    ]
    controls = [
        {
            "control_id": control.control_id,
            "requirement_id": control.requirement_id,
            "expected_pass": control.expected_pass,
            "source": control.source,
            "reviewed_by": control.reviewed_by,
            "partition": control.partition,
            "case_id": control.case_id,
            "rationale": control.rationale,
            "contributed_by": control.contributed_by,
            "independent": control.independent,
            "evidence": {
                "input": control.test_case.input,
                "actual_output": control.test_case.actual_output,
                "expected_output": control.test_case.expected_output,
                "context": control.test_case.context,
                "metadata": control.test_case.metadata,
            },
        }
        for control in suite.controls
    ]
    rows = []
    if operation == "run":
        for case in suite.cases:
            if profile not in case.profiles:
                continue
            for trial in range(1, config.trials + 1):
                for req in case.requirements:
                    for repetition in range(1, config.grader_repetitions + 1):
                        rows.append(
                            {
                                "id": f"run:{case.case_id}:{req}:t{trial}:r{repetition}",
                                "case_id": case.case_id,
                                "requirement_id": req,
                                "trial": trial,
                                "repetition": repetition,
                            }
                        )
    elif operation == "audit":
        for control in suite.controls:
            if control.partition != "validation":
                continue
            for repetition in range(1, config.grader_repetitions + 1):
                rows.append(
                    {
                        "id": f"audit:{control.control_id}:{control.requirement_id}:r{repetition}",
                        "case_id": control.control_id,
                        "control_id": control.control_id,
                        "requirement_id": control.requirement_id,
                        "trial": 1,
                        "repetition": repetition,
                        "expected_pass": control.expected_pass,
                    }
                )
    return {
        "cases": cases,
        "controls": controls,
        "metrics": metrics,
        "gaps": (
            control_gaps
            if operation == "audit"
            else application_gaps
            if operation == "run"
            else control_gaps + application_gaps + review_gaps
        ),
        "control_gaps": control_gaps,
        "application_gaps": application_gaps,
        "review_gaps": review_gaps,
        "expected_ids": [row["id"] for row in rows],
        "expected_rows": rows,
    }


def _application_case(project: Project, case: Case, target: str, trial: int):
    from deepeval.test_case import LLMTestCase

    config = project.contract.targets[target]
    request = {
        "case_id": case.case_id,
        "input": case.test_case.input,
        "context": case.test_case.context or [],
        "fixture": case.fixture,
        "trial": trial,
    }
    started = time.monotonic()
    response = invoke_target(
        config.command,
        request,
        cwd=project.root,
        env_names=config.env,
        timeout_seconds=config.timeout_seconds,
    )
    elapsed = time.monotonic() - started
    protected = {"fixture", "case_id", "elapsed_seconds"} | (case.test_case.metadata or {}).keys()
    if protected & response.get("metadata", {}).keys():
        raise TargetError("protocol", "Target metadata collides with evaluator-owned metadata.")
    # Expected answers/tools and native grading metadata remain evaluator-only.
    data = case.test_case.model_dump()
    data.update(response)
    data["completion_time"] = elapsed
    data["metadata"] = {
        **(case.test_case.metadata or {}),
        **response.get("metadata", {}),
        "fixture": copy.deepcopy(case.fixture),
        "case_id": case.case_id,
        "elapsed_seconds": elapsed,
    }
    try:
        return LLMTestCase.model_validate(data)
    except Exception:
        raise TargetError("protocol", "Target output is not a valid native test case.") from None


def _run(payload: dict, emit) -> None:
    project = Project(Path(payload["root"]), payload["change"])
    operation, profile = payload["operation"], payload["profile"]
    suite, metrics = _load(project)
    plan = _plan(project, suite, metrics, operation, profile)
    emit("plan", plan)
    finish: dict[str, Any] = {
        "gaps": list(plan["gaps"]),
        "execution_errors": [],
        "observed_cost_usd": 0.0,
    }
    config = project.contract.profiles[profile]
    if operation == "inspect":
        emit("complete", finish)
        return
    if len(plan["expected_ids"]) > config.max_observations:
        finish["execution_errors"].append(
            "Observation plan exceeds max_observations; no calls made"
        )
        emit("complete", finish)
        return
    paid = any(metrics[row["requirement_id"]]["requires_paid"] for row in plan["expected_rows"])
    if paid and (not payload["allow_paid"] or config.max_cost_usd <= 0):
        finish["execution_errors"].append(
            "Provider-backed grading requires --allow-paid and a positive budget"
        )
        emit("complete", finish)
        return
    cases = {case.case_id: case for case in suite.cases}
    controls = {control.control_id: control for control in suite.controls}
    previous = None
    native = None
    target_error = None
    seen_metrics: weakref.WeakValueDictionary[int, Any] = weakref.WeakValueDictionary()
    for row in plan["expected_rows"]:
        if operation == "run":
            key = row["case_id"], row["trial"]
            if key != previous:
                target_error = None
                try:
                    native = _application_case(project, cases[key[0]], payload["target"], key[1])
                except TargetError as exc:
                    target_error = f"target_{exc.code}: {exc}"
                    native = None
                previous = key
        else:
            native = controls[row["control_id"]].test_case
        if target_error:
            result = {
                "passed": None,
                "error": target_error,
                "score": None,
                "reason": None,
                "cost_usd": None,
            }
        else:

            def checked_factory(requirement_id=row["requirement_id"]):
                factory = suite.metrics[requirement_id]
                metric = factory()
                if id(metric) in seen_metrics:
                    raise ProjectError("Metric factory reused an instance across observations")
                seen_metrics[id(metric)] = metric
                if _metric_info(lambda: metric, require_fresh=False) != metrics[requirement_id]:
                    raise ProjectError("Metric configuration changed after preflight")
                return metric

            result = grade(checked_factory, copy.deepcopy(native))
        observation = {
            **row,
            **result,
            "actual_output": native.actual_output if native else None,
            "metadata": (native.metadata or {}) if native else {},
        }
        if native:
            observation.update(
                {
                    name: native.model_dump(mode="json")[name]
                    for name in ("context", "retrieval_context", "tools_called")
                }
            )
        if operation == "audit":
            observation["observed_passed"] = result["passed"]
            observation["passed"] = (
                result["passed"] is row["expected_pass"] if type(result["passed"]) is bool else None
            )
        _check_imports(project)
        emit("observation", observation)
        cost = result["cost_usd"]
        if cost is not None:
            finish["observed_cost_usd"] += cost
        elif not target_error:
            finish["gaps"].append("A grader returned unknown cost; no further calls scheduled")
            break
        if cost and (not payload["allow_paid"] or config.max_cost_usd <= 0):
            finish["execution_errors"].append("A declared offline metric reported paid execution")
            break
        if config.max_cost_usd > 0 and finish["observed_cost_usd"] >= config.max_cost_usd:
            if row != plan["expected_rows"][-1]:
                finish["gaps"].append(
                    "Observed cost budget reached; remaining observations not scheduled"
                )
            break
    emit("complete", finish)


def main() -> None:
    protocol = sys.stdout

    def emit(kind, data):
        protocol.write(json.dumps({"type": kind, "data": data}, allow_nan=False) + "\n")
        protocol.flush()

    def terminate(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        payload = json.loads(sys.stdin.buffer.read(65_537))
        # User suites and metrics may print arbitrary text or credentials. Their
        # output is not evidence and must not contaminate the protocol or logs.
        with (
            open(os.devnull, "w") as discard,
            contextlib.redirect_stdout(discard),
            contextlib.redirect_stderr(discard),
        ):
            _run(payload, emit)
    except ProjectError as exc:
        emit("complete", {"execution_errors": [str(exc)]})
    except KeyboardInterrupt:
        emit("complete", {"execution_errors": ["Evaluator operation was interrupted"]})
    except BaseException:
        emit("complete", {"execution_errors": ["Evaluator suite loading or execution failed"]})


if __name__ == "__main__":
    main()
