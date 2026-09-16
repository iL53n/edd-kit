"""Exercise the installed distribution from an unrelated, disposable project."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def smoke(python: str) -> None:
    with tempfile.TemporaryDirectory(prefix="edd-installed-") as scratch:
        root = Path(scratch).resolve()

        def invoke(*arguments: str, expected: int = 0) -> dict:
            result = subprocess.run(
                [python, "-I", "-m", "edd_kit", "--root", str(root), *arguments, "--json"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            if result.returncode != expected:
                raise AssertionError(
                    f"{arguments}: exit {result.returncode}, expected {expected}\n"
                    f"{result.stdout}\n{result.stderr}"
                )
            return json.loads(result.stdout)

        imported = subprocess.run(
            [python, "-I", "-c", "import edd_kit; print(edd_kit.__file__)"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        if Path(imported.stdout.strip()).is_relative_to(
            Path(__file__).resolve().parents[1] / "src"
        ):
            raise AssertionError("Smoke test imported the editable source instead of the wheel")
        invoke("doctor")
        demo = invoke("demo")
        assert demo["demonstrated"] and demo["checks"]["wrong_owner_change"] == "DETECTED"
        invoke("init", "--agent", "codex")
        assert (root / ".agents/skills/edd-prepare/references/authoring.md").is_file()
        assert (root / ".agents/skills/edd-prepare/references/acceptance.md").is_file()
        invoke("prepare", "orders", "--template", "cancellation", "--brief", "Synthetic wheel test")
        assert (root / "evals/orders/eval-requirements.lock").is_file()
        assert invoke("inspect", "orders")["execution_errors"] == []
        measured_baseline = invoke("measure", "orders", "--target", "stub", "--stage", "baseline")
        assert measured_baseline["execution_status"] == "COMPLETE"
        assert measured_baseline["behavior_decision"] == "FAIL"
        assert (root / measured_baseline["report_paths"]["markdown"]).is_file()
        measured_candidate = invoke(
            "measure",
            "orders",
            "--target",
            "candidate",
            "--compare-to",
            measured_baseline["run_id"],
        )
        assert measured_candidate["comparison"]["status"] == "comparable"
        assert invoke("status", "orders")["mode"] == "measurement"
        packet = invoke("review", "orders")
        assert packet["kind"] == "review-packet" and packet["controls"][0]["evidence"]
        written = invoke("review", "orders", "--write")
        assert written["kind"] == "review-packet-written"
        invoke(
            "review",
            "orders",
            "--area",
            "domain",
            "--decision",
            "approve",
            "--by",
            "Distribution test fixture reviewer",
            "--note",
            "The synthetic expectations represent this packaging fixture",
            "--criteria-digest",
            packet["criteria_digest"],
        )
        audit = invoke("audit", "orders")
        assert audit["completed"] == 5
        invoke(
            "review",
            "orders",
            "--area",
            "technical",
            "--decision",
            "approve",
            "--by",
            "Distribution test fixture reviewer",
            "--note",
            "The passing audit measures this synthetic fixture only",
            "--criteria-digest",
            packet["criteria_digest"],
        )
        baseline = invoke("run", "orders", "--target", "stub", "--stage", "baseline", expected=1)
        assert baseline["target_kind"] == "stub" and baseline["errors"] == 0
        status = invoke("status", "orders", "--acceptance")
        assert status["ready_to_build"] and status["workflow"]["phase"] == "build"
        assert invoke("check", "orders", "--target", "candidate")["decision"] == "PASS"
        invoke("run", "orders", "--target", "wrong-owner", expected=1)
        invoke("verify", "orders", expected=1)
        invoke("run", "orders", "--target", "candidate")
        assert invoke("verify", "orders")["comparison"]["status"] == "comparable"
        target = root / "targets/orders/candidate.py"
        target.write_text(target.read_text() + "\n# Candidate revision changed.\n")
        assert invoke("verify", "orders", expected=3)["candidate"]["status"] == "stale"
        invoke("run", "orders", "--target", "candidate")
        invoke("verify", "orders")
        (root / "evals/orders/new-rubric.md").write_text("New evaluation criterion.\n")
        assert invoke("verify", "orders", expected=3)["review"]["status"] == "stale"
        draft = invoke("prepare", "draft", "--brief", "A domain feature requiring authoring")
        assert draft["authoring_required"]
        draft_audit = invoke("audit", "draft")
        assert draft_audit["decision"] == "PASS"
        draft_status = invoke("status", "draft", "--acceptance")
        assert not draft_status["ready_to_build"] and not draft_status["accepted"]
        inferred = invoke("run", "draft", expected=1)
        assert inferred["target"] == "candidate"
        print(
            json.dumps(
                {
                    "installed_package": imported.stdout.strip(),
                    "result": "PASS",
                    "checks": [
                        "packaged skills and lock",
                        "development measurement and comparison",
                        "isolated guided demo",
                        "review packet and workflow status",
                        "separate domain and technical review gates",
                        "consolidated acceptance report",
                        "native audit",
                        "stub baseline",
                        "candidate acceptance",
                        "defect detection",
                        "target/criteria drift",
                        "unreviewed draft cannot pass",
                        "unambiguous target inference",
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument(
        "--python", required=True, help="Python from the isolated wheel environment"
    )
    smoke(arguments.parse_args().python)
