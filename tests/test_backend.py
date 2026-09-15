"""Grading tests use native DeepEval classes without any provider calls."""

import importlib.metadata

import pytest

from edd_kit.backend import grade

# Import EDD first so DeepEval's implicit telemetry and dotenv loading are disabled.
# isort: split
from deepeval.metrics import BaseMetric, GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import ConversationalTestCase, LLMTestCase, SingleTurnParams, Turn


class ExactMetric(BaseMetric):
    def __init__(self):
        self.threshold = 1.0
        self.async_mode = False

    def measure(self, test_case):
        self.score = 1.0 if test_case.actual_output == test_case.expected_output else 0.0
        self.reason = "Exact answer comparison."
        return self.score


@pytest.mark.parametrize("provider_score,passed", [(10, True), (0, False)])
def test_native_geval_normalizes_provider_response_with_fixed_reviewed_steps(
    provider_score, passed
):
    class OfflineTransport(DeepEvalBaseLLM):
        """Stub only the provider seam; real GEval owns prompts, scoring and success."""

        def load_model(self):
            return self

        def generate(self, prompt, schema=None, **kwargs):
            assert "actual output" in prompt.lower()
            return schema(score=provider_score, reason="Synthetic provider transport response")

        async def a_generate(self, prompt, schema=None, **kwargs):
            return self.generate(prompt, schema=schema, **kwargs)

        def get_model_name(self):
            return "offline-transport-fixture"

    result = grade(
        lambda: GEval(
            name="Correctness",
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
            evaluation_steps=["Compare actual output with the expected factual answer."],
            model=OfflineTransport(),
            async_mode=False,
            threshold=0.8,
        ),
        LLMTestCase(input="Name the capital", actual_output="Paris", expected_output="Paris"),
    )
    assert result["error"] is None
    assert result["passed"] is passed
    assert result["score"] == (1.0 if passed else 0.0)
    assert result["cost_usd"] is None  # A custom transport does not supply native cost accounting.


def test_native_deepeval_metric_grades_application_output():
    result = grade(
        ExactMetric,
        LLMTestCase(input="Say hello", actual_output="hello", expected_output="hello"),
    )

    assert result == {
        "score": 1.0,
        "passed": True,
        "reason": "Exact answer comparison.",
        "error": None,
        "cost_usd": None,
    }


@pytest.mark.parametrize("score", [None, True, "1.0", -0.1, 1.1, float("nan"), float("inf")])
def test_invalid_metric_scores_cannot_become_grading_evidence(score):
    class InvalidMetric(ExactMetric):
        def measure(self, test_case):
            self.score = score
            return self.score

    result = grade(InvalidMetric, LLMTestCase(input="prompt", actual_output="response"))

    assert result["passed"] is None
    assert result["score"] is None
    assert result["error"] is not None


def test_previous_metric_attributes_cannot_satisfy_a_missing_measurement():
    class StaleMetric(ExactMetric):
        score = 1.0
        success = True
        reason = "Old successful observation."
        evaluation_cost = 12.0

        def measure(self, test_case):
            return None

    result = grade(StaleMetric, LLMTestCase(input="prompt", actual_output="response"))

    assert result["error"] is not None
    assert result["score"] is None
    assert result["reason"] is None
    assert result["cost_usd"] is None


@pytest.mark.parametrize("failure_location", ["factory", "measure", "reported_error"])
def test_grader_failure_is_an_error_and_does_not_expose_exception_contents(failure_location):
    secret = "provider-key-and-private-response"

    class BrokenMetric(ExactMetric):
        def measure(self, test_case):
            if failure_location == "measure":
                raise RuntimeError(secret)
            self.score = 1.0
            self.error = secret
            return self.score

    def factory():
        if failure_location == "factory":
            raise RuntimeError(secret)
        return BrokenMetric()

    result = grade(factory, LLMTestCase(input="prompt", actual_output="response"))

    assert result["passed"] is None
    assert result["error"] is not None
    assert secret not in repr(result)


@pytest.mark.parametrize("threshold", [True, "1.0", -0.1, 1.1, float("nan"), float("inf")])
def test_invalid_thresholds_are_configuration_errors(threshold):
    def factory():
        metric = ExactMetric()
        metric.threshold = threshold
        return metric

    result = grade(factory, LLMTestCase(input="prompt", actual_output="response"))

    assert result["error"] is not None
    assert result["passed"] is None


def test_a_custom_success_method_cannot_disagree_with_the_declared_threshold():
    class DishonestMetric(ExactMetric):
        def is_successful(self):
            return True

    result = grade(
        DishonestMetric,
        LLMTestCase(input="prompt", actual_output="wrong", expected_output="right"),
    )

    assert result["error"] is not None
    assert result["passed"] is None


def test_score_only_metric_has_no_pass_opinion():
    def factory():
        metric = ExactMetric()
        metric.threshold = None
        return metric

    result = grade(
        factory, LLMTestCase(input="prompt", actual_output="wrong", expected_output="right")
    )

    assert result["score"] == 0.0
    assert result["passed"] is None
    assert result["error"] is None


def test_unsupported_deepeval_version_is_refused(monkeypatch):
    monkeypatch.setattr(importlib.metadata, "version", lambda distribution: "999.0.0")
    result = grade(ExactMetric, LLMTestCase(input="prompt", actual_output="response"))

    assert result["error"].startswith("unsupported_backend:")


def test_conversation_is_not_silently_treated_as_a_single_turn():
    conversation = ConversationalTestCase(turns=[Turn(role="user", content="hello")])
    result = grade(ExactMetric, conversation)

    assert result["error"].startswith("unsupported_case:")


def test_non_deepeval_metric_is_refused_even_if_it_looks_compatible():
    class OtherMetric:
        threshold = 1.0

        def measure(self, test_case):
            self.score = 1.0

        def is_successful(self):
            return True

    result = grade(OtherMetric, LLMTestCase(input="prompt", actual_output="response"))

    assert result["error"].startswith("unsupported_metric:")


@pytest.mark.parametrize("flag", ["flaky", "requires_trace"])
def test_unsupported_metric_modes_do_not_silently_weaken_grading(flag):
    def factory():
        metric = ExactMetric()
        setattr(metric, flag, True)
        return metric

    result = grade(factory, LLMTestCase(input="prompt", actual_output="response"))

    assert result["error"].startswith("unsupported_metric:")


@pytest.mark.parametrize("cost", [-1, True, "0", float("nan"), float("inf")])
def test_invalid_cost_is_not_accepted_as_accounting_evidence(cost):
    class BadCostMetric(ExactMetric):
        def measure(self, test_case):
            super().measure(test_case)
            self.evaluation_cost = cost
            return self.score

    result = grade(BadCostMetric, LLMTestCase(input="prompt", actual_output="response"))

    assert result["error"] is not None
    assert result["cost_usd"] is None


def test_metric_may_not_change_its_threshold_while_measuring():
    class MovingThresholdMetric(ExactMetric):
        def measure(self, test_case):
            self.threshold = 0.0
            return super().measure(test_case)

    result = grade(MovingThresholdMetric, LLMTestCase(input="prompt", actual_output="response"))

    assert result["error"] is not None


def test_keyboard_interrupt_is_not_misreported_as_a_metric_result():
    class CancelledMetric(ExactMetric):
        def measure(self, test_case):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        grade(CancelledMetric, LLMTestCase(input="prompt", actual_output="response"))


def test_success_method_cannot_change_the_validated_result():
    class MovingResultMetric(ExactMetric):
        def is_successful(self):
            self.score = float("nan")
            return False

    result = grade(
        MovingResultMetric,
        LLMTestCase(input="prompt", actual_output="same", expected_output="same"),
    )

    assert result["error"] is not None
    assert result["score"] is None


def test_reported_success_attribute_cannot_disagree_with_score():
    class InconsistentSuccessMetric(ExactMetric):
        def measure(self, test_case):
            super().measure(test_case)
            self.success = False

    result = grade(
        InconsistentSuccessMetric,
        LLMTestCase(input="prompt", actual_output="same", expected_output="same"),
    )

    assert result["error"] is not None
    assert result["passed"] is None
