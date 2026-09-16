"""Executable example only: replace these semantics before approving the feature."""

import json
from pathlib import Path

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from edd_kit import Case, Control, Suite


class ExampleAcknowledgement(BaseMetric):
    threshold: float

    def __init__(self):
        self.threshold = 1.0
        self.flaky = False
        self.async_mode = True
        self.error = None
        self.evaluation_cost = 0.0

    def measure(self, test_case, *args, **kwargs):
        self.error = None
        self.evaluation_cost = 0.0
        self.score = None
        self.success = False
        if test_case.actual_output is None or test_case.expected_output is None:
            self.error = "The example requires both observed and expected output."
            raise ValueError(self.error)
        self.score = float(test_case.actual_output == test_case.expected_output)
        self.success = self.score >= self.threshold
        self.reason = (
            "Exact example acknowledgement matched."
            if self.success
            else "Example acknowledgement did not match."
        )
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case)

    def is_successful(self):
        return self.error is None and self.score is not None and self.score >= self.threshold

    @property
    def __name__(self):
        return "example-acknowledgement"


def build_suite():
    directory = Path(__file__).parent
    rows = json.loads((directory / "cases.json").read_text())
    controls = json.loads((directory / "controls.json").read_text())
    return Suite(
        cases=[
            Case(
                case_id=row["id"],
                test_case=LLMTestCase(input=row["input"], expected_output=row["expected_output"]),
                requirements=tuple(row["requirements"]),
                fixture=row["fixture"],
                description=row["description"],
                expected_behavior=row["expected_behavior"],
                acceptable_alternatives=tuple(row["acceptable_alternatives"]),
                unacceptable_behaviors=tuple(row["unacceptable_behaviors"]),
                source=row.get("source", "unknown"),
                expectation_source=row.get("expectation_source", "unknown"),
                deferred_reason=row.get("deferred_reason"),
            )
            for row in rows
        ],
        controls=[
            Control(
                control_id=row["id"],
                requirement_id=row["requirement_id"],
                test_case=LLMTestCase(
                    input=row["input"],
                    actual_output=row["actual_output"],
                    expected_output=row["expected_output"],
                ),
                expected_pass=row["expected_pass"],
                source=row["source"],
                reviewed_by=row["reviewed_by"],
                partition=row["partition"],
                case_id=row["case_id"],
                rationale=row["rationale"],
                contributed_by=row["contributed_by"],
                independent=row["independent"],
            )
            for row in controls
        ],
        metrics={"example-acknowledgement": ExampleAcknowledgement},
    )
