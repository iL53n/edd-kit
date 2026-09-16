"""Synthetic worked examples, evaluated using native deterministic DeepEval metrics."""

import json
from copy import deepcopy
from pathlib import Path

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from edd_kit import Case, Control, Suite


def _rows(filename):
    return json.loads(Path(__file__).with_name(filename).read_text())


class OrderStateMetric(BaseMetric):
    threshold: float

    def __init__(self, requirement):
        self.requirement = requirement
        self.threshold = 1.0
        self.flaky = False
        self.async_mode = True
        self.error = None
        self.evaluation_cost = 0.0
        self.expected = {row["id"]: row["expected_state"] for row in _rows("cases.json")}

    def measure(self, test_case, *args, **kwargs):
        self.error = None
        self.evaluation_cost = 0.0
        self.score = None
        self.success = False
        try:
            metadata = test_case.metadata or {}
            fixture = metadata["fixture"]
            before = fixture["orders"]
            after = metadata["state_after"]
            if not isinstance(after, dict) or not isinstance(before, dict):
                raise ValueError("Order state must be an object keyed by order ID.")
            for order in after.values():
                if not isinstance(order, dict) or set(order) != {"owner", "status"}:
                    raise ValueError("Observed orders must contain owner and status.")
            if self.requirement == "correct-order-state":
                passed = after == self.expected[metadata["case_id"]]
                self.reason = (
                    "Observed state matches the worked example."
                    if passed
                    else "Observed state differs from the required order outcome."
                )
            else:
                events = metadata["events"]
                if not isinstance(events, list):
                    raise ValueError("Action history must be a list.")
                replay = deepcopy(before)
                authorized_history = True
                for event in events:
                    if not isinstance(event, dict) or set(event) != {"order_id", "before", "after"}:
                        raise ValueError("Malformed action history event.")
                    order_id = event["order_id"]
                    if order_id not in replay or event["before"] != replay[order_id]:
                        raise ValueError(
                            "Action history does not match initial/intermediate state."
                        )
                    next_order = event["after"]
                    if not isinstance(next_order, dict) or set(next_order) != {"owner", "status"}:
                        raise ValueError("Action history contains invalid order state.")
                    if (
                        before[order_id]["owner"] != fixture["user_id"]
                        and next_order != replay[order_id]
                    ):
                        authorized_history = False
                    replay[order_id] = next_order
                if replay != after:
                    raise ValueError("Action history does not account for the resulting state.")
                passed = (
                    set(before) == set(after)
                    and all(
                        after[order_id] == order
                        for order_id, order in before.items()
                        if order["owner"] != fixture["user_id"]
                    )
                    and authorized_history
                )
                self.reason = (
                    "Other customers' orders were unchanged throughout the operation."
                    if passed
                    else "Another customer's order was changed or removed."
                )
            self.score = float(passed)
            self.success = passed
            return self.score
        except (KeyError, TypeError, ValueError) as exc:
            self.error = f"Missing or invalid state evidence: {exc}"
            raise ValueError(self.error) from exc

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case)

    def is_successful(self):
        return self.error is None and self.score is not None and self.score >= self.threshold

    @property
    def __name__(self):
        return self.requirement


def outcome_metric():
    return OrderStateMetric("correct-order-state")


def ownership_metric():
    return OrderStateMetric("preserve-other-customers-orders")


def build_suite():
    rows = _rows("cases.json")
    by_id = {row["id"]: row for row in rows}
    requirements = ("correct-order-state", "preserve-other-customers-orders")
    cases = [
        Case(
            case_id=row["id"],
            test_case=LLMTestCase(input=row["input"], metadata={"case_id": row["id"]}),
            requirements=requirements,
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
    ]
    controls = []
    for row in _rows("controls.json"):
        example = by_id[row["case_id"]]
        controls.append(
            Control(
                control_id=row["id"],
                requirement_id=row["requirement_id"],
                test_case=LLMTestCase(
                    input=example["input"],
                    actual_output=row["actual_output"],
                    metadata={
                        "case_id": row["case_id"],
                        "fixture": example["fixture"],
                        "state_after": row["state_after"],
                        "events": row["events"],
                    },
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
        )
    return Suite(
        cases=cases,
        controls=controls,
        metrics={
            "correct-order-state": outcome_metric,
            "preserve-other-customers-orders": ownership_metric,
        },
    )
