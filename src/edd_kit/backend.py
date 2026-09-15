"""Normalize native single-turn DeepEval grading without hosted reporting."""

from __future__ import annotations

import importlib.metadata
import math
import os
from collections.abc import Callable
from numbers import Real
from typing import TypeGuard

# Set these before importing DeepEval: it loads dotenv and tracing at import time.
os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"
os.environ["DEEPEVAL_UPDATE_WARNING_OPT_IN"] = "0"
os.environ["CONFIDENT_TRACE_FLUSH"] = "0"
os.environ["CONFIDENT_TRACE_SAMPLE_RATE"] = "0"
os.environ.pop("CONFIDENT_API_KEY", None)

SUPPORTED_DEEPEVAL_VERSION = "4.2.3"


def _error(message: str) -> dict:
    return {"score": None, "passed": None, "reason": None, "error": message, "cost_usd": None}


def _number(value: object) -> TypeGuard[float]:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def grade(metric_factory: Callable, test_case: object) -> dict:
    """Create a metric and return its observation; the caller applies gate policy."""
    try:
        if importlib.metadata.version("deepeval") != SUPPORTED_DEEPEVAL_VERSION:
            return _error("unsupported_backend: DeepEval 4.2.3 is required")
    except importlib.metadata.PackageNotFoundError:
        return _error("unsupported_backend: DeepEval 4.2.3 is required")
    try:
        from deepeval.metrics import BaseMetric
        from deepeval.test_case import LLMTestCase

        if not isinstance(test_case, LLMTestCase) or test_case.multimodal:
            return _error("unsupported_case: a text single-turn LLMTestCase is required")
        metric = metric_factory()
        if not isinstance(metric, BaseMetric):
            return _error("unsupported_metric: a native single-turn BaseMetric is required")
        if metric.flaky or metric.requires_trace:
            return _error("unsupported_metric: flaky and trace-dependent metrics are not supported")
        threshold = metric.threshold
        if threshold is not None and (not _number(threshold) or not 0 <= threshold <= 1):
            return _error("invalid_metric: threshold must be finite and between zero and one")
        for attribute in ("score", "success", "reason", "error", "evaluation_cost"):
            setattr(metric, attribute, None)
        metric.skipped = False
        metric.measure(test_case)
        if metric.error is not None or metric.skipped:
            return _error("metric_error: grader reported an execution error")
        if metric.threshold != threshold:
            return _error("invalid_metric: threshold changed while grading")
        if not _number(metric.score) or not 0 <= metric.score <= 1:
            return _error("invalid_metric: score must be finite and between zero and one")
        measured_score = metric.score
        measured_success = metric.success
        passed = metric.is_successful()
        if (
            metric.score != measured_score
            or metric.threshold != threshold
            or metric.error is not None
            or metric.skipped
        ):
            return _error("invalid_metric: success evaluation changed the measured result")
        expected = None if threshold is None else bool(metric.score >= threshold)
        if passed is not expected:
            return _error("invalid_metric: success disagrees with the declared score and threshold")
        if (measured_success is not None and measured_success is not expected) or (
            metric.success is not None and metric.success is not expected
        ):
            return _error("invalid_metric: reported success disagrees with the measured result")
        if metric.reason is not None and not isinstance(metric.reason, str):
            return _error("invalid_metric: reason must be text or absent")
        cost = metric.evaluation_cost
        if cost is not None and (not _number(cost) or cost < 0):
            return _error("invalid_metric: cost must be finite and nonnegative")
        return {
            "score": float(metric.score),
            "passed": passed,
            "reason": metric.reason,
            "error": None,
            "cost_usd": None if cost is None else float(cost),
        }
    except Exception:
        return _error("metric_error: grader construction or execution failed")
