"""Replay independent agent-authored fixtures through an installed EDD distribution.

This verifies retained artifacts, not agent behavior or production-domain approval.
The original generation/build observations are documented with the example.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def smoke(python: str, source: Path) -> None:
    interpreter = Path(python).absolute()
    env = {**os.environ, "PATH": f"{interpreter.parent}{os.pathsep}{os.environ.get('PATH', '')}"}
    env.update(DEEPEVAL_DISABLE_DOTENV="1", DEEPEVAL_TELEMETRY_OPT_OUT="1")
    with tempfile.TemporaryDirectory(prefix="edd-independent-") as scratch:
        root = Path(scratch).resolve() / "project"
        shutil.copytree(source, root, ignore=shutil.ignore_patterns(".edd", "__pycache__"))

        def invoke(project: Path, *arguments: str, expected: int = 0) -> dict:
            result = subprocess.run(
                [
                    str(interpreter),
                    "-I",
                    "-m",
                    "edd_kit",
                    "--root",
                    str(project),
                    *arguments,
                    "--json",
                ],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode != expected:
                raise AssertionError(
                    f"{arguments}: {result.returncode}\n{result.stdout}\n{result.stderr}"
                )
            return json.loads(result.stdout)

        def check_script(project: Path, *arguments: str) -> None:
            subprocess.run(
                [str(interpreter), "-I", *arguments],
                cwd=project,
                env=env,
                check=True,
                timeout=60,
                capture_output=True,
                text=True,
            )

        snapshots = {}
        for project, change, baseline_target, observations, validation, failed in (
            (root, "invoice-extraction", "stub", 36, 14, 16),
            (root / "brownfield", "inline-total", "current", 18, 8, 7),
        ):
            invoke(project, "init", "--agent", "none")
            assert invoke(project, "verify", change, expected=3)["review"]["status"] == "missing"
            inspection = invoke(project, "inspect", change)
            assert not inspection["execution_errors"] and not inspection["review_gaps"]
            assert inspection["review_packet_status"] == "missing"
            snapshots[change] = inspection["criteria_digest"]
            check_script(project, f"evals/{change}/harness_checks.py")
            packet = invoke(project, "review", change)
            written = invoke(project, "review", change, "--write")
            assert written["kind"] == "review-packet-written"
            assert invoke(project, "inspect", change)["review_packet_status"] == "current"
            invoke(
                project,
                "review",
                change,
                "--area",
                "domain",
                "--decision",
                "approve",
                "--by",
                "Automated synthetic fixture check",
                "--note",
                "Synthetic fixture expectations only; not production-domain approval",
                "--criteria-digest",
                packet["criteria_digest"],
            )
            audit = invoke(project, "audit", change)
            assert audit["completed"] == validation and audit["errors"] == 0
            invoke(
                project,
                "review",
                change,
                "--area",
                "technical",
                "--decision",
                "approve",
                "--by",
                "Automated synthetic fixture check",
                "--note",
                "Passing synthetic controls measure this retained fixture only",
                "--criteria-digest",
                packet["criteria_digest"],
            )
            baseline = invoke(
                project,
                "run",
                change,
                "--target",
                baseline_target,
                "--stage",
                "baseline",
                expected=1,
            )
            assert baseline["completed"] == observations and baseline["errors"] == 0
            assert sum(row["passed"] is False for row in baseline["observations"]) == failed
            assert baseline["target_kind"] == ("stub" if project == root else "application")
            assert invoke(project, "status", change)["ready_to_build"] is True

        check_script(root, "-m", "unittest", "discover", "-s", "tests", "-v")
        candidate = root / "targets/invoice-extraction/candidate.py"
        before = hashlib.sha256(candidate.read_bytes()).hexdigest()
        result = invoke(root, "check", "invoice-extraction", "--target", "candidate")
        assert result["decision"] == "PASS"
        assert result["comparison"]["status"] == "comparable"
        assert result["comparison"]["baseline_kind"] == "stub"
        assert hashlib.sha256(candidate.read_bytes()).hexdigest() == before
        assert invoke(root, "status", "invoice-extraction")["accepted"] is True
        assert not invoke(root / "brownfield", "status", "inline-total")["accepted"]
        assert (root / "brownfield/app/target.py").read_bytes() == candidate.read_bytes()
        for project, change in (
            (root, "invoice-extraction"),
            (root / "brownfield", "inline-total"),
        ):
            assert invoke(project, "inspect", change)["criteria_digest"] == snapshots[change]
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "invoice": {"audit": 14, "baseline_violations": 16, "accepted": True},
                    "brownfield": {
                        "audit": 8,
                        "baseline_violations": 7,
                        "application_unchanged": True,
                    },
                    "criteria_unchanged": True,
                    "scope": "Retained independent synthetic fixtures; no provider calls",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, help="Installed-wheel Python interpreter")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "examples/invoice-extraction",
    )
    args = parser.parse_args()
    smoke(args.python, args.source)
