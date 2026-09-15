"""Check fixture/source preservation independently of model self-report."""

import json
import sys
from pathlib import Path

from edd_kit.target import invoke_target

directory = Path(__file__).resolve().parent
before = (directory / "cases.json").read_bytes()
rows = json.loads(before.decode("utf-8"))
for row in rows:
    response = invoke_target(
        [sys.executable, str(directory / "input_probe.py")],
        {"input": row["input"], "fixture": {}, "case_id": row["id"], "trial": 0},
        cwd=directory,
        env_names=[],
        timeout_seconds=10,
    )
    assert response["actual_output"] == row["input"], row["id"]
assert (directory / "cases.json").read_bytes() == before
print(f"Preserved all input characters and fixture bytes for {len(rows)} synthetic invoices.")
