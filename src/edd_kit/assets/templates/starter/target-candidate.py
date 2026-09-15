"""Replace this placeholder with an adapter to your actual application."""

import json
import sys

request = json.load(sys.stdin)
print(json.dumps({"actual_output": "Feature not implemented.", "metadata": {}}))
