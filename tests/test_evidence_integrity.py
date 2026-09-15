import json
from pathlib import Path

import pytest

from edd_kit.decisions import decide
from edd_kit.engine import Workflow
from edd_kit.evidence import new_id, read_record, timestamp, write_record
from edd_kit.models import Requirement
from edd_kit.project import Project, ProjectError, digest
from edd_kit.scaffold import init_project, prepare_change


def test_environment_redaction_preserves_identity_while_removing_observed_values(
    tmp_path, monkeypatch
):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Synthetic cancellation", "cancellation")
    contract_path = tmp_path / "evals/orders/contract.json"
    contract = json.loads(contract_path.read_text())
    contract["targets"]["candidate"]["env"] = ["APP_MODE"]
    contract_path.write_text(json.dumps(contract))
    monkeypatch.setenv("APP_MODE", "candidate")
    target = tmp_path / "targets/orders/candidate.py"
    target.write_text(
        target.read_text().replace('"events": events', '"events": events, "debug": "candidate"')
    )
    workflow = Workflow(tmp_path, "orders")
    assert workflow.audit()["decision"] == "PASS"
    packet = workflow.review_packet()
    workflow.write_review_packet()
    workflow.record_review(
        area="domain",
        decision="approve",
        reviewer="Test reviewer",
        rationale="Reviewed synthetic cancellation cases",
        criteria_digest=packet["criteria_digest"],
    )
    workflow.record_review(
        area="technical",
        decision="approve",
        reviewer="Test reviewer",
        rationale="Reviewed the passing audit",
        criteria_digest=packet["criteria_digest"],
    )
    result = workflow.run("candidate")
    assert result["target"] == "candidate"
    assert result["observations"][0]["metadata"]["debug"] == "[REDACTED]"
    assert workflow.verify()["decision"] == "PASS"


def test_inspect_redacts_credentials_in_native_metric_configuration(tmp_path, monkeypatch):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Synthetic cancellation", "cancellation")
    contract_path = tmp_path / "evals/orders/contract.json"
    contract = json.loads(contract_path.read_text())
    contract["evaluator_env"] = ["EDD_TEST_SECRET"]
    contract_path.write_text(json.dumps(contract))
    monkeypatch.setenv("EDD_TEST_SECRET", "synthetic-private-value")
    suite = tmp_path / "evals/orders/suite.py"
    suite.write_text(
        suite.read_text().replace(
            "self.threshold = 1.0",
            "self.threshold = 1.0\n"
            '        self.criteria = __import__("os").environ["EDD_TEST_SECRET"]',
        )
    )
    report = Workflow(tmp_path, "orders").inspect()
    assert not report.get("execution_errors")
    assert report["metrics"]
    assert "synthetic-private-value" not in json.dumps(report)
    assert report["metrics"]["correct-order-state"]["criteria"] == "[REDACTED]"


def test_control_audit_uses_control_coverage_not_application_sample_minimum():
    requirements = [Requirement(id="correct", description="Correct", min_cases=100)]
    observations = [
        {
            "id": "good",
            "requirement_id": "correct",
            "case_id": "good",
            "passed": True,
            "error": None,
        },
        {"id": "bad", "requirement_id": "correct", "case_id": "bad", "passed": True, "error": None},
    ]
    result = decide(requirements, ["good", "bad"], observations, audit=True)
    assert result["decision"] == "PASS"
    assert decide(requirements, ["good", "bad"], observations)["decision"] == "INCONCLUSIVE"


@pytest.mark.parametrize("invalid", [{}, {"id": []}, {"id": "one", "passed": True}])
def test_malformed_observation_metadata_fails_closed_without_crashing(invalid):
    requirement = Requirement(id="correct", description="Correct")
    result = decide([requirement], ["one"], [invalid])
    assert result["decision"] == "ERROR"
    assert result["integrity_errors"]


def test_record_round_trip_detects_payload_corruption(tmp_path: Path):
    path = tmp_path / "run.json"
    original = {"kind": "candidate", "observations": [{"id": "one", "passed": False}]}
    write_record(path, original)
    assert read_record(path) == original
    envelope = json.loads(path.read_text())
    envelope["payload"]["observations"][0]["passed"] = True
    path.write_text(json.dumps(envelope))
    with pytest.raises(ProjectError, match="corrupted"):
        read_record(path)


def test_record_rejects_overflowed_json_number_as_a_structured_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version":1,"payload":{"score":1e999},"sha256":"unused"}')
    with pytest.raises(ProjectError):
        read_record(path)


@pytest.mark.parametrize("operation", ["read", "write"])
def test_record_io_rejects_symlink_in_any_evidence_ancestor(tmp_path: Path, operation: str):
    outside = tmp_path / "outside"
    outside.mkdir()
    actual = outside / "history" / "run.json"
    write_record(actual, {"decision": "FAIL"})
    original = actual.read_bytes()
    link = tmp_path / "linked"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ProjectError, match="symlink"):
        if operation == "read":
            read_record(link / "history" / "run.json")
        else:
            write_record(link / "history" / "run.json", {"decision": "PASS"})
    assert actual.read_bytes() == original


def _observations(passed: bool, *, audit: bool = False) -> list[dict]:
    return [
        {
            "id": case,
            "case_id": case,
            "requirement_id": "example-acknowledgement",
            "trial": 1,
            "repetition": 1,
            "passed": passed,
            "error": None,
            "metadata": {},
            **(
                {
                    "control_id": case,
                    "expected_pass": case == "positive-control",
                    "observed_passed": (case == "positive-control")
                    if passed
                    else (case != "positive-control"),
                }
                if audit
                else {}
            ),
        }
        for case in (["positive-control", "negative-control"] if audit else ["example-case"])
    ]


def _save_run(project: Project, kind: str, passed: bool) -> tuple[Path, dict]:
    observations = _observations(passed, audit=kind == "audit")
    identity = project.bundle_identity()
    target = None if kind == "audit" else "candidate"
    record = {
        "schema_version": 1,
        "id": new_id(),
        "created_at": timestamp(),
        "finished_at": timestamp(),
        "kind": kind,
        "change": project.change,
        "profile": "acceptance",
        "bundle_identity": identity,
        "bundle_digest": digest(identity),
        "criteria_digest": project.criteria_digest(),
        "target": target,
        "target_kind": "application" if target else None,
        "target_identity": project.target_identity(target) if target else None,
        "target_digest": project.target_digest(target) if target else None,
        "execution_policy": project.contract.profiles["acceptance"].model_dump(),
        "observations": observations,
        "expected_ids": [row["id"] for row in observations],
        "expected_rows": [
            {
                key: value
                for key, value in row.items()
                if key
                in {
                    "id",
                    "case_id",
                    "requirement_id",
                    "trial",
                    "repetition",
                    "control_id",
                    "expected_pass",
                }
            }
            for row in observations
        ],
        "execution_errors": [],
        "gaps": [],
    }
    record.update(
        decide(
            project.contract.requirements,
            record["expected_ids"],
            observations,
            audit=kind == "audit",
        )
    )
    path = project.state / "runs" / f"{record['id']}.json"
    write_record(path, record)
    return path, record


def _reviewed_project(root: Path) -> tuple[Project, Workflow]:
    init_project(root, "none")
    prepare_change(root, "feature", "A literal persistence-test fixture.")
    workflow = Workflow(root, "feature")
    packet = workflow.review_packet()
    workflow.write_review_packet()
    workflow.record_review(
        area="domain",
        decision="approve",
        reviewer="Test reviewer",
        rationale="Reviewing the explicit persistence fixture, not a product",
        criteria_digest=packet["criteria_digest"],
    )
    assert workflow.audit()["decision"] == "PASS"
    workflow.record_review(
        area="technical",
        decision="approve",
        reviewer="Test reviewer",
        rationale="The passing audit measures the persistence fixture",
        criteria_digest=packet["criteria_digest"],
    )
    return Project(root, "feature"), workflow


def test_stale_target_failure_does_not_imply_current_application_failure(tmp_path: Path):
    project, workflow = _reviewed_project(tmp_path)
    _save_run(project, "audit", True)
    _save_run(project, "candidate", False)
    assert workflow.verify()["decision"] == "FAIL"
    target = tmp_path / "targets" / "feature" / "candidate.py"
    target.write_text(target.read_text() + "\n# Implemented code changed after this observation.\n")
    result = workflow.verify()
    assert result["decision"] == "INCONCLUSIVE"
    assert result["candidate"]["status"] == "stale"
    assert result["review"]["status"] == "current"
    assert result["audit"]["status"] == "current"


def test_verify_recomputes_decision_instead_of_trusting_saved_summary(tmp_path: Path):
    project, workflow = _reviewed_project(tmp_path)
    _save_run(project, "audit", True)
    path, record = _save_run(project, "candidate", False)
    record["decision"] = "PASS"
    record["requirements"]["example-acknowledgement"]["pass_rate"] = 1.0
    write_record(path, record)
    assert workflow.verify()["decision"] == "FAIL"


@pytest.mark.parametrize("mutation", ["kind", "profile", "policy", "identity", "identity-digest"])
def test_verify_rejects_invalid_run_metadata_even_with_valid_checksum(
    tmp_path: Path, mutation: str
):
    project, workflow = _reviewed_project(tmp_path)
    path, record = _save_run(project, "candidate", True)
    if mutation == "kind":
        record["kind"] = "publish"
    elif mutation == "profile":
        record["profile"] = "production"
    elif mutation == "policy":
        record["execution_policy"] = {}
    elif mutation == "identity":
        record.pop("bundle_identity")
    else:
        record["bundle_digest"] = "0" * 64
    write_record(path, record)
    with pytest.raises(ProjectError, match="run metadata|identity|policy"):
        workflow.verify()


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "empty"])
def test_verify_recomputes_corrupted_observation_coverage(tmp_path: Path, mutation: str):
    project, workflow = _reviewed_project(tmp_path)
    _save_run(project, "audit", True)
    path, record = _save_run(project, "candidate", True)
    if mutation == "missing":
        record["observations"] = []
    elif mutation == "duplicate":
        record["observations"] *= 2
    else:
        record["observations"] = [{}]
    write_record(path, record)
    result = workflow.verify()
    assert result["decision"] == ("INCONCLUSIVE" if mutation == "missing" else "ERROR")


def test_review_does_not_approve_changed_criteria(tmp_path: Path):
    project, workflow = _reviewed_project(tmp_path)
    _save_run(project, "audit", True)
    _save_run(project, "candidate", True)
    assert workflow.verify()["decision"] == "PASS"
    (project.directory / "brief.md").write_text("Changed acceptance intent.\n")
    result = workflow.verify()
    assert result["review"]["status"] == "stale"
    assert result["decision"] == "INCONCLUSIVE"


def test_explicit_unavailable_baseline_allows_build_without_fabricating_a_score(tmp_path: Path):
    project, workflow = _reviewed_project(tmp_path)
    _save_run(project, "audit", True)
    assert workflow.status()["ready_to_build"] is False
    record = workflow.baseline_unavailable(
        "New capability; no existing system can execute these cases."
    )
    result = workflow.status()
    assert record["kind"] == "baseline-unavailable"
    assert "observations" not in record
    assert result["ready_to_build"] is True
    assert result["baseline"]["decision"] == "UNAVAILABLE"
    assert result["comparison"]["status"] == "unavailable"
    _save_run(project, "baseline", False)
    assert workflow.status()["baseline"]["decision"] == "FAIL"
    workflow.baseline_unavailable("Replacing the earlier baseline choice after review.")
    assert workflow.status()["baseline"]["decision"] == "UNAVAILABLE"


def test_baseline_execution_error_is_not_an_explicit_unavailable_decision(tmp_path: Path):
    project, workflow = _reviewed_project(tmp_path)
    _save_run(project, "audit", True)
    path, record = _save_run(project, "baseline", True)
    record["observations"][0].update(passed=None, error="Target timed out")
    write_record(path, record)
    assert workflow.status()["baseline"]["decision"] == "ERROR"
    assert workflow.status()["ready_to_build"] is False


@pytest.mark.parametrize("mutation", ["case", "trial", "metadata", "missing-plan"])
def test_verify_binds_observations_to_the_saved_execution_plan(tmp_path: Path, mutation: str):
    project, workflow = _reviewed_project(tmp_path)
    _save_run(project, "audit", True)
    path, record = _save_run(project, "candidate", True)
    if mutation == "case":
        record["observations"][0]["case_id"] = "unplanned-case"
    elif mutation == "trial":
        record["observations"][0]["trial"] = 99
    elif mutation == "metadata":
        record["observations"][0]["metadata"] = []
    else:
        record.pop("expected_rows")
    write_record(path, record)
    assert workflow.verify()["decision"] == "ERROR"


def test_review_metadata_requires_meaningful_text_not_truthy_objects(tmp_path: Path):
    project, workflow = _reviewed_project(tmp_path)
    path = project.directory / "review.json"
    record = json.loads(path.read_text())
    record["versions"][0]["events"][0]["reviewer"] = {"name": "Not a reviewer string"}
    path.write_text(json.dumps(record))
    with pytest.raises(ProjectError, match="review metadata"):
        workflow.verify()


def test_review_history_cannot_write_through_a_symlink(tmp_path: Path):
    project, workflow = _reviewed_project(tmp_path)
    original = (project.directory / "review.json").read_bytes()
    history = project.state / "reviews"
    moved = project.state / "old-reviews"
    history.rename(moved)
    outside = tmp_path / "outside"
    outside.mkdir()
    history.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ProjectError, match="symlink"):
        workflow.record_review(
            area="domain",
            decision="needs_discussion",
            reviewer="Another reviewer",
            rationale="A review must not follow linked history directories",
            criteria_digest=project.criteria_digest(),
            subject="case:example-acknowledgement",
        )
    assert list(outside.iterdir()) == []
    assert (project.directory / "review.json").read_bytes() == original


def test_run_persists_complete_evaluator_and_scoped_source_identity(tmp_path: Path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Synthetic cancellation reference", "cancellation")
    workflow = Workflow(tmp_path, "orders")
    run = workflow.audit()
    assert run["decision"] == "PASS"
    assert run["bundle_identity"] == workflow.project.bundle_identity()
    assert run["bundle_digest"] == digest(run["bundle_identity"])
    assert run["source_identity"]["declared_files"]
    assert "git_revision" in run["source_identity"]
    assert "git_status" in run["source_identity"]
    assert run["metrics"]["correct-order-state"]["threshold"] == 1.0
    assert run["expected_rows"]
    persisted = read_record(workflow.project.state / "runs" / f"{run['id']}.json")
    assert persisted == json.loads(json.dumps(run))


def test_run_preserves_observations_when_target_disappears_during_execution(tmp_path: Path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "Test an application that changes its own code.")
    target = tmp_path / "targets" / "feature" / "candidate.py"
    target.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        "json.load(sys.stdin)\nPath(__file__).unlink()\n"
        "print(json.dumps({'actual_output': 'Example acknowledged.', 'metadata': {}}))\n"
    )
    workflow = Workflow(tmp_path, "feature")
    record = workflow.run("candidate")
    assert record["decision"] == "ERROR"
    assert record["observations"]
    assert record["execution_errors"]
    assert not target.exists()
    assert read_record(workflow.project.state / "runs" / f"{record['id']}.json")["observations"]
