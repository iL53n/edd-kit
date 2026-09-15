"""Offline toy application: fixture state is not production state attestation."""

import json
import sys

request = json.load(sys.stdin)
fixture = request["fixture"]
orders = fixture["orders"]
order = orders[fixture["order_id"]]
events = []
if order["owner"] != fixture["user_id"]:
    output = "That order does not belong to you."
elif order["status"] == "cancelled":
    output = "Order was already cancelled."
else:
    before = dict(order)
    order["status"] = "cancelled"
    events.append({"order_id": fixture["order_id"], "before": before, "after": dict(order)})
    output = "Order cancelled."
print(json.dumps({"actual_output": output, "metadata": {"state_after": orders, "events": events}}))
