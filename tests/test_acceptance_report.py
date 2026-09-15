import json
import os
import subprocess
import sys

from edd_kit.engine import Workflow
from edd_kit.scaffold import init_project, prepare_change


def _accepted_workflow(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Cancel owned orders", "cancellation")
    workflow = Workflow(tmp_path, "orders")
    packet = workflow.review_packet()
    workflow.write_review_packet()
    workflow.record_review(
        area="domain",
        decision="approve",
        reviewer="Order specialist",
        rationale="The scenarios represent the cancellation policy.",
        criteria_digest=packet["criteria_digest"],
    )
    audit = workflow.audit()
    workflow.record_review(
        area="technical",
        decision="approve",
        reviewer="Evaluation engineer",
        rationale="The audit demonstrates the declared known failures are rejected.",
        criteria_digest=packet["criteria_digest"],
    )
    candidate = workflow.run("candidate", stage="candidate")
    return workflow, audit, candidate


def test_acceptance_report_combines_review_execution_and_freshness(tmp_path):
    workflow, audit, candidate = _accepted_workflow(tmp_path)

    report = workflow.acceptance_report(
        fresh_run_ids={audit["id"], candidate["id"]}, application_revision="abc123"
    )

    assert report["kind"] == "acceptance-report"
    assert report["decision"] == "PASS"
    assert report["review"]["domain"]["status"] == "approved"
    assert report["review"]["technical"]["status"] == "approved"
    assert report["evidence"]["audit"]["origin"] == "fresh"
    assert report["evidence"]["candidate"]["origin"] == "fresh"
    assert report["application"]["revision"] == "abc123"
    assert report["criteria_digest"] == workflow.project.criteria_digest()
    assert report["cases"][0]["expected_behavior"]
    assert report["cases"][0]["observations"][0]["actual_output"]
    assert report["controls"][0]["observed_passed"] is not None
    assert "does not prove universal grader reliability" in report["limitation"]
    assert "# EDD acceptance report" in report["markdown"]


def test_saved_report_and_written_bundle_are_explicit(tmp_path):
    workflow, _, _ = _accepted_workflow(tmp_path)

    report = workflow.acceptance_report()
    paths = workflow.write_acceptance_report(".edd/orders/report", report)

    assert report["evidence"]["audit"]["origin"] == "saved"
    assert report["evidence"]["candidate"]["origin"] == "saved"
    assert paths["markdown"] == ".edd/orders/report/report.md"
    assert paths["json"] == ".edd/orders/report/report.json"
    persisted = json.loads((tmp_path / paths["json"]).read_text())
    assert persisted["markdown"] == report["markdown"]


def test_check_returns_fresh_report_even_when_candidate_fails(tmp_path):
    workflow, _, _ = _accepted_workflow(tmp_path)

    result = workflow.check(
        "noop",
        report_dir=".edd/orders/check-report",
        application_revision="def456",
    )

    assert result["decision"] == "FAIL"
    assert result["report"]["decision"] == "FAIL"
    assert result["report"]["evidence"]["audit"]["origin"] == "fresh"
    assert result["report"]["evidence"]["candidate"]["origin"] == "fresh"
    assert (tmp_path / ".edd/orders/check-report/report.md").is_file()


def test_cli_can_export_saved_acceptance_report(tmp_path):
    workflow, _, _ = _accepted_workflow(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "edd_kit",
            "--root",
            str(tmp_path),
            "report",
            "orders",
            "--acceptance",
            "--output-dir",
            ".edd/orders/cli-report",
            "--revision",
            "commit789",
            "--json",
        ],
        text=True,
        capture_output=True,
        timeout=30,
        env={**os.environ, "DEEPEVAL_DISABLE_DOTENV": "1", "DEEPEVAL_TELEMETRY_OPT_OUT": "1"},
    )

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["application"]["revision"] == "commit789"
    assert payload["report_paths"]["markdown"] == ".edd/orders/cli-report/report.md"
