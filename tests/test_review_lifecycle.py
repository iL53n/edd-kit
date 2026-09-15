import json

import pytest

from edd_kit.engine import Workflow
from edd_kit.evidence import write_record
from edd_kit.project import ProjectError
from edd_kit.scaffold import init_project, prepare_change


def _starter(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "A specialist-readable behavior", "starter")
    return Workflow(tmp_path, "feature")


def test_review_packet_is_specialist_readable_and_can_be_committed(tmp_path):
    workflow = _starter(tmp_path)

    packet = workflow.review_packet()
    case = packet["cases"][0]
    control = packet["controls"][0]

    assert case["description"] == "A user requests the example acknowledgement"
    assert case["expected_behavior"] == "Return the exact acknowledgement text"
    assert case["reference_output"] == "Example acknowledged."
    assert control["rationale"]
    assert control["contributed_by"]
    assert control["independent"] is True
    assert "## Domain expectations" in packet["markdown"]
    assert "## Technical validation" in packet["markdown"]
    assert "Passing these controls does not prove" in packet["markdown"]

    path = workflow.write_review_packet()
    assert path == tmp_path / "evals" / "feature" / "REVIEW.md"
    assert path.read_text() == packet["markdown"]
    assert workflow.inspect()["review_packet_status"] == "current"


def test_review_packet_is_excluded_from_criteria_but_staleness_is_visible(tmp_path):
    workflow = _starter(tmp_path)
    before = workflow.project.criteria_digest()
    path = workflow.write_review_packet()

    path.write_text(path.read_text().replace("Domain expectations", "Old expectations"))

    assert workflow.project.criteria_digest() == before
    inspection = workflow.inspect()
    assert inspection["review_packet_status"] == "stale"
    assert any("REVIEW.md is stale" in gap for gap in inspection["gaps"])


def test_review_packet_with_embedded_crlf_remains_current(tmp_path):
    workflow = _starter(tmp_path)
    cases_path = tmp_path / "evals" / "feature" / "cases.json"
    cases = json.loads(cases_path.read_text())
    cases[0]["input"] = "First invoice line\r\nSecond invoice line\r\n"
    cases_path.write_text(json.dumps(cases, indent=2) + "\n")

    workflow.write_review_packet()

    assert workflow.inspect()["review_packet_status"] == "current"


def test_review_packet_json_contains_no_opaque_python_requirement(tmp_path):
    workflow = _starter(tmp_path)
    packet = workflow.review_packet()

    json.dumps(packet)
    assert packet["criteria_digest"]
    assert packet["cases"][0]["input"]
    assert packet["requirements"]["example-acknowledgement"]["description"]


def test_feedback_requires_explicit_criteria_revision_and_both_approvals(tmp_path):
    workflow = _starter(tmp_path)
    packet = workflow.review_packet()
    workflow.write_review_packet()

    feedback = workflow.record_review(
        area="domain",
        decision="request_changes",
        reviewer="Domain specialist",
        rationale="The expected wording should acknowledge the request clearly.",
        criteria_digest=packet["criteria_digest"],
        subject="case:example-acknowledgement",
    )
    assert feedback["review"]["status"] == "pending"
    assert workflow.status()["ready_to_build"] is False

    cases_path = tmp_path / "evals" / "feature" / "cases.json"
    cases = json.loads(cases_path.read_text())
    cases[0]["expected_behavior"] = "Clearly acknowledge the request with the exact text"
    cases_path.write_text(json.dumps(cases, indent=2) + "\n")

    revised = workflow.review_packet()
    assert revised["criteria_digest"] != packet["criteria_digest"]
    assert any(
        row["subject"] == "case:example-acknowledgement" and row["field"] == "expected_behavior"
        for row in revised["revision_diff"]
    )
    assert "Return the exact acknowledgement text" in revised["markdown"]
    assert "Clearly acknowledge the request with the exact text" in revised["markdown"]
    workflow.write_review_packet()
    workflow.record_review(
        area="domain",
        decision="approve",
        reviewer="Domain specialist",
        rationale="The revised behavior represents the business rule.",
        criteria_digest=revised["criteria_digest"],
    )
    assert workflow.status()["review"]["domain"]["status"] == "approved"
    assert workflow.status()["review"]["technical"]["status"] == "missing"

    with pytest.raises(ProjectError, match="passing audit"):
        workflow.record_review(
            area="technical",
            decision="approve",
            reviewer="Evaluation engineer",
            rationale="The controls measure the approved rule.",
            criteria_digest=revised["criteria_digest"],
        )

    assert workflow.audit()["decision"] == "PASS"
    workflow.record_review(
        area="technical",
        decision="approve",
        reviewer="Evaluation engineer",
        rationale="The passing audit and controls measure the approved rule.",
        criteria_digest=revised["criteria_digest"],
    )
    assert workflow.status()["review"]["status"] == "current"

    log = json.loads((tmp_path / "evals" / "feature" / "review.json").read_text())
    assert log["schema_version"] == 2
    assert len(log["versions"]) == 2
    assert log["versions"][0]["events"][0]["subject"] == "case:example-acknowledgement"


def test_needs_discussion_after_approval_reopens_the_area(tmp_path):
    workflow = _starter(tmp_path)
    packet = workflow.review_packet()
    workflow.write_review_packet()
    workflow.record_review(
        area="domain",
        decision="approve",
        reviewer="Specialist",
        rationale="Approved.",
        criteria_digest=packet["criteria_digest"],
    )
    workflow.record_review(
        area="domain",
        decision="needs_discussion",
        reviewer="Specialist",
        rationale="We need to decide whether equivalent wording is acceptable.",
        criteria_digest=packet["criteria_digest"],
        subject="case:example-acknowledgement",
    )

    review = workflow.status()["review"]
    assert review["domain"]["status"] == "needs_discussion"
    assert review["blockers"][0]["subject"] == "case:example-acknowledgement"


def test_schema_v1_review_is_visible_but_cannot_satisfy_new_gates(tmp_path):
    workflow = _starter(tmp_path)
    write_record(
        tmp_path / "evals" / "feature" / "review.json",
        {
            "schema_version": 1,
            "kind": "review",
            "id": "legacy-review",
            "created_at": "2026-01-01T00:00:00+00:00",
            "change": "feature",
            "criteria_digest": workflow.project.criteria_digest(),
            "reviewer": "Legacy reviewer",
            "note": "Old combined approval",
        },
    )

    review = workflow.status()["review"]
    assert review["status"] == "legacy"
    assert workflow.verify()["decision"] != "PASS"


def test_stale_committed_packet_blocks_acceptance_even_when_evidence_is_current(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Cancel owned orders", "cancellation")
    workflow = Workflow(tmp_path, "orders")
    packet = workflow.review_packet()
    workflow.write_review_packet()
    workflow.record_review(
        area="domain",
        decision="approve",
        reviewer="Specialist",
        rationale="Approved domain meaning.",
        criteria_digest=packet["criteria_digest"],
    )
    assert workflow.audit()["decision"] == "PASS"
    workflow.record_review(
        area="technical",
        decision="approve",
        reviewer="Engineer",
        rationale="Approved technical validation.",
        criteria_digest=packet["criteria_digest"],
    )
    assert workflow.run("candidate")["decision"] == "PASS"
    assert workflow.verify()["decision"] == "PASS"

    review_path = tmp_path / "evals" / "orders" / "REVIEW.md"
    review_path.write_text(review_path.read_text() + "manually changed\n")

    result = workflow.verify()
    assert result["decision"] == "INCONCLUSIVE"
    assert result["review_packet"]["status"] == "stale"
