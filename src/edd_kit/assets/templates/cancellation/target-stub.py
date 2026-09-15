"""Meaningful baseline: executes correctly while leaving the capability absent."""

import json
import sys

request = json.load(sys.stdin)
print(
    json.dumps(
        {
            "actual_output": "Cancellation is not implemented.",
            "metadata": {"state_after": request["fixture"]["orders"], "events": []},
        }
    )
)
