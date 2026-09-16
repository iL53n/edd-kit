import json

from test_cli import command

from edd_kit.engine import Workflow
from edd_kit.scaffold import init_project, prepare_change


def test_measure_returns_behavior_failure_as_completed_measurement(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "Measure a behavior", "starter")

    result = command(
        tmp_path,
        "measure",
        "feature",
        "--target",
        "candidate",
        "--report-dir",
        ".edd/feature/measurement",
        "--json",
    )

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "measurement-report"
    assert payload["execution_status"] == "COMPLETE"
    assert payload["behavior_decision"] == "FAIL"
    assert payload["cases"][0]["observations"][0]["actual_output"]
    assert (tmp_path / ".edd/feature/measurement/report.md").is_file()
    status = json.loads(command(tmp_path, "status", "feature", "--json").stdout)
    assert status["latest_measurement"]["execution_status"] == "COMPLETE"
    assert status["latest_measurement"]["behavior_decision"] == "FAIL"


def test_measure_writes_default_report_and_does_not_require_controls(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "Measure a behavior", "starter")
    (tmp_path / "evals" / "feature" / "controls.json").write_text("[]\n")

    result = command(tmp_path, "measure", "feature", "--target", "candidate", "--json")

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["execution_status"] == "COMPLETE"
    report_path = tmp_path / payload["report_paths"]["markdown"]
    assert report_path.is_file()
    assert "measurement" in report_path.read_text()


def test_compare_reports_deltas_only_for_matching_measurement_conditions(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Cancel owned orders", "cancellation")
    workflow = Workflow(tmp_path, "orders")
    before = workflow.measure("stub", stage="baseline")["run_id"]
    after = workflow.measure("candidate")["run_id"]

    comparison = workflow.compare_runs(before, after)

    assert comparison["status"] == "comparable"
    assert comparison["improved_requirements"]
    assert comparison["changed_observations"]


def test_compare_command_reads_saved_measurements(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Cancel owned orders", "cancellation")
    workflow = Workflow(tmp_path, "orders")
    before = workflow.measure("stub", stage="baseline")["run_id"]
    after = workflow.measure("candidate")["run_id"]

    result = command(
        tmp_path,
        "compare",
        "orders",
        "--before",
        before,
        "--after",
        after,
        "--json",
    )

    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "comparable"


def test_changed_scenario_set_is_visible_and_not_numerically_compared(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "Measure a behavior", "starter")
    workflow = Workflow(tmp_path, "feature")
    before = workflow.measure("candidate")["run_id"]
    cases_path = tmp_path / "evals" / "feature" / "cases.json"
    cases = json.loads(cases_path.read_text())
    cases.append(
        {
            **cases[0],
            "id": "uncertain-example",
            "input": "An unresolved scenario",
            "expected_output": None,
            "source": "synthetic",
            "expectation_source": "unknown",
            "deferred_reason": "The acceptable outcome needs a product decision.",
        }
    )
    cases_path.write_text(json.dumps(cases, indent=2) + "\n")
    after = workflow.measure("candidate")["run_id"]

    comparison = workflow.compare_runs(before, after)
    report = workflow.measurement_report(workflow.run_record(after), comparison=comparison)

    assert comparison["status"] == "unavailable"
    assert comparison["case_changes"]["added"] == ["uncertain-example"]
    assert report["deferred_count"] == 1
    assert report["expected"] == 1


def test_all_deferred_scenarios_are_inconclusive_without_becoming_execution_errors(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "Measure a behavior", "starter")
    cases_path = tmp_path / "evals" / "feature" / "cases.json"
    cases = json.loads(cases_path.read_text())
    cases[0]["deferred_reason"] = "A domain owner must decide the expected behavior."
    cases_path.write_text(json.dumps(cases, indent=2) + "\n")

    result = command(tmp_path, "measure", "feature", "--target", "candidate", "--json")

    assert result.returncode == 3, result.stdout
    payload = json.loads(result.stdout)
    assert payload["execution_status"] == "INCONCLUSIVE"
    assert payload["behavior_decision"] == "INCONCLUSIVE"
    assert payload["deferred_count"] == 1


def test_saved_run_is_summarized_with_its_saved_requirements(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "Measure a behavior", "starter")
    workflow = Workflow(tmp_path, "feature")
    run_id = workflow.measure("candidate")["run_id"]
    contract_path = tmp_path / "evals" / "feature" / "contract.json"
    contract = json.loads(contract_path.read_text())
    contract["requirements"][0]["critical"] = False
    contract["requirements"][0]["pass_rate"] = 0.01
    contract_path.write_text(json.dumps(contract, indent=2) + "\n")

    saved = workflow.run_record(run_id)

    assert saved["decision"] == "FAIL"
    assert saved["requirements"]["example-acknowledgement"]["critical"] is True


def test_default_status_guides_measurement_and_acceptance_remains_explicit(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "Measure a behavior", "starter")

    measured = json.loads(command(tmp_path, "status", "feature", "--json").stdout)
    strict = json.loads(command(tmp_path, "status", "feature", "--acceptance", "--json").stdout)

    assert measured["mode"] == "measurement"
    assert measured["workflow"]["phase"] == "measure"
    assert measured["acceptance"]["optional"] is True
    assert strict["ready_to_build"] is False
