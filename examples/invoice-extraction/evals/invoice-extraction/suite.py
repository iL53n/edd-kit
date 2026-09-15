"""Offline invoice acceptance criteria. Reference labels are proposals, not approval.

This contains grading logic only: it compares observed fields to worked examples
and does not parse source invoices to implement production extraction.
"""

import json
import re
from decimal import Decimal
from functools import partial
from pathlib import Path

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from edd_kit import Case, Control, Suite

DIRECTORY = Path(__file__).resolve().parent
REQUIREMENTS = ("output-schema", "correct-currency", "correct-total")
SOURCE = "Unreviewed synthetic worked example drafted from the user's invoice-extraction brief."
DECIMAL = re.compile(r"-?[0-9]+\.[0-9]{2}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _object(text):
    if not isinstance(text, str):
        raise ValueError("Output must be text containing a JSON object")
    value = json.loads(text, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("Output must be a JSON object")
    return value


def _total_shape(value):
    return value is None or (isinstance(value, str) and DECIMAL.fullmatch(value) is not None)


def _valid_shape(value):
    return (
        set(value) == {"currency", "total"}
        and value["currency"] in ("USD", "EUR", None)
        and _total_shape(value["total"])
    )


class InvoiceMetric(BaseMetric):
    def __init__(self, requirement):
        self.requirement = requirement
        self.threshold = 1.0
        self.async_mode = True
        self.strict_mode = True
        self.error = None
        self.evaluation_cost = 0.0

    def measure(self, test_case, *args, **kwargs):
        self.score = None
        self.success = None
        self.reason = None
        self.error = None
        self.evaluation_cost = 0.0
        try:
            expected = _object(test_case.expected_output)
            if not _valid_shape(expected):
                raise ValueError("Malformed proposed reference")
        except (TypeError, ValueError) as exc:
            self.error = f"Invalid evaluator reference: {exc}"
            raise ValueError(self.error) from exc
        try:
            actual = _object(test_case.actual_output)
        except (TypeError, ValueError):
            actual = {}

        if self.requirement == "output-schema":
            success = _valid_shape(actual)
        elif self.requirement == "correct-currency":
            success = "currency" in actual and actual["currency"] == expected["currency"]
        elif self.requirement == "correct-total":
            success = "total" in actual and _total_shape(actual["total"])
            if success:
                observed = actual["total"]
                reference = expected["total"]
                success = (
                    observed is reference
                    if observed is None or reference is None
                    else Decimal(observed) == Decimal(reference)
                )
        else:
            self.error = "Unknown metric requirement"
            raise ValueError(self.error)
        self.success = bool(success)
        self.score = float(self.success)
        result = (
            "satisfies this proposed criterion"
            if self.success
            else "contradicts this proposed criterion"
        )
        self.reason = f"{self.requirement}: {result}"
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self):
        return self.error is None and self.success is True

    @property
    def __name__(self):
        return self.requirement


def build_suite():
    rows = json.loads((DIRECTORY / "cases.json").read_bytes().decode("utf-8"))
    controls = json.loads((DIRECTORY / "controls.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}
    return Suite(
        cases=[
            Case(
                case_id=row["id"],
                test_case=LLMTestCase(
                    input=row["input"],
                    expected_output=json.dumps(row["expected"]),
                    additional_metadata={"golden_source": SOURCE},
                ),
                requirements=REQUIREMENTS,
                profiles=tuple(row["profiles"]),
                fixture={},
                description=f"Invoice extraction scenario {row['id']}.",
                expected_behavior=(
                    f"Return currency {row['expected']['currency']} and total "
                    f"{row['expected']['total']} without inventing absent fields."
                ),
                unacceptable_behaviors=("Return fields inconsistent with the reviewed reference.",),
            )
            for row in rows
        ],
        controls=[
            Control(
                control_id=row["id"],
                requirement_id=row["requirement_id"],
                test_case=LLMTestCase(
                    input=by_id[row["case_id"]]["input"],
                    expected_output=json.dumps(by_id[row["case_id"]]["expected"]),
                    actual_output=row["actual_output"],
                ),
                expected_pass=row["expected_pass"],
                source=SOURCE,
                reviewed_by=row["reviewed_by"],
                partition=row["partition"],
                case_id=row["case_id"],
                rationale=(
                    "Known acceptable output for this requirement."
                    if row["expected_pass"]
                    else "Plausible but incorrect output that this grader must reject."
                ),
                contributed_by=row["reviewed_by"],
                independent=True,
            )
            for row in controls
        ],
        metrics={name: partial(InvoiceMetric, name) for name in REQUIREMENTS},
    )
