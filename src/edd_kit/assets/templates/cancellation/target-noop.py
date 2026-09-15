"""Deliberate defect: claim success without performing the state transition."""

import json
import sys

request = json.load(sys.stdin)
print(
    json.dumps(
        {
            "actual_output": "Order cancelled.",
            "metadata": {"state_after": request["fixture"]["orders"], "events": []},
        }
    )
)
