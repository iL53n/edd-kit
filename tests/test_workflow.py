import pytest

import edd_kit.engine as engine_module
from edd_kit.engine import Workflow
from edd_kit.project import ProjectError
from edd_kit.scaffold import init_project, prepare_change


def test_prepare_baseline_implement_acceptance_lifecycle(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Cancel eligible orders", "cancellation")
    workflow = Workflow(tmp_path, "orders")
    assert workflow.audit()["decision"] == "PASS"
    packet = workflow.review_packet()
    workflow.write_review_packet()
    workflow.record_review(
        area="domain",
        decision="approve",
        reviewer="Synthetic fixture reviewer",
        rationale="Reviewed worked examples for the offline demo",
        criteria_digest=packet["criteria_digest"],
    )
    workflow.record_review(
        area="technical",
        decision="approve",
        reviewer="Synthetic fixture reviewer",
        rationale="Reviewed the passing control audit for the offline demo",
        criteria_digest=packet["criteria_digest"],
    )
    baseline = workflow.run("stub", stage="baseline")
    assert baseline["decision"] == "FAIL"
    build_status = workflow.status()
    assert build_status["ready_to_build"] is True
    assert build_status["workflow"]["phase"] == "build"
    assert build_status["workflow"]["state"] == "ready"
    assert build_status["actions"][0]["actor"] == "developer"
    assert build_status["actions"][0]["command"].endswith("--target candidate")
    assert workflow.run("candidate", stage="candidate")["decision"] == "PASS"
    result = workflow.verify()
    assert result["decision"] == "PASS"
    assert result["comparison"]["status"] == "comparable"
    assert result["comparison"]["improved_requirements"]
    completed = workflow.status()
    assert completed["workflow"]["phase"] == "complete"
    assert completed["actions"] == []

    target = tmp_path / "targets" / "orders" / "candidate.py"
    target.write_text(target.read_text() + "\n# Subsequent application revision.\n")
    stale = workflow.status()
    assert stale["review"]["status"] == "current"
    assert stale["audit"]["status"] == "current"
    assert stale["candidate"]["status"] == "stale"
    assert (tmp_path / "evals" / "orders" / "suite.py").is_file()
    assert workflow.run("candidate")["decision"] == "PASS"


def test_unreviewed_starter_cannot_be_accepted(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "A new feature", "starter")
    workflow = Workflow(tmp_path, "feature")
    assert workflow.audit()["decision"] == "PASS"
    assert workflow.verify()["decision"] != "PASS"
    status = workflow.status()
    assert "edd review feature" in status["next_steps"][0]
    assert not any("Candidate" in step for step in status["next_steps"])
    assert any("baseline" in step for step in status["next_steps"])


def test_workflow_rejects_explicit_symlinked_root(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    init_project(actual, "none")
    prepare_change(actual, "orders", "Cancel eligible orders", "cancellation")
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ProjectError, match="symlink"):
        Workflow(linked, "orders").status()


def test_review_decision_rolls_back_when_history_write_fails(tmp_path, monkeypatch):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "A behavior", "starter")
    workflow = Workflow(tmp_path, "feature")
    packet = workflow.review_packet()
    workflow.write_review_packet()

    def fail_write(path, payload):
        raise OSError("synthetic history failure")

    monkeypatch.setattr(engine_module, "write_record", fail_write)
    with pytest.raises(OSError, match="synthetic"):
        workflow.record_review(
            area="domain",
            decision="approve",
            reviewer="Reviewer",
            rationale="Reviewed current examples",
            criteria_digest=packet["criteria_digest"],
        )

    assert not (tmp_path / "evals" / "feature" / "review.json").exists()
    assert not list((tmp_path / ".edd" / "feature" / "reviews").glob("*.json"))


def test_domain_feedback_rejects_technical_control_subject(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "A behavior", "starter")
    workflow = Workflow(tmp_path, "feature")
    packet = workflow.review_packet()
    workflow.write_review_packet()

    with pytest.raises(ProjectError, match="requirement or case"):
        workflow.record_review(
            area="domain",
            decision="request_changes",
            reviewer="Reviewer",
            rationale="This is technical feedback.",
            criteria_digest=packet["criteria_digest"],
            subject="control:example-good",
        )
