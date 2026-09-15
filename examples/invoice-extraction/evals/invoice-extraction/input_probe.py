"""Test-only lossless transport probe, never an extraction implementation."""

import json
import sys

request = json.load(sys.stdin)
print(json.dumps({"actual_output": request["input"]}))
