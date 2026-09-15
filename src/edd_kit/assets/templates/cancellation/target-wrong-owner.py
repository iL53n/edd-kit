"""Deliberate defect: mutate the requested order without checking its owner."""

import json
import sys

request = json.load(sys.stdin)
fixture = request["fixture"]
before = dict(fixture["orders"][fixture["order_id"]])
fixture["orders"][fixture["order_id"]]["status"] = "cancelled"
events = [
    {
        "order_id": fixture["order_id"],
        "before": before,
        "after": dict(fixture["orders"][fixture["order_id"]]),
    }
]
print(
    json.dumps(
        {
            "actual_output": "Order cancelled.",
            "metadata": {"state_after": fixture["orders"], "events": events},
        }
    )
)
