"""A runnable absence-of-capability baseline, not an import failure."""

import json
import sys

json.load(sys.stdin)
print(json.dumps({"actual_output": "Feature not implemented.", "metadata": {}}))
