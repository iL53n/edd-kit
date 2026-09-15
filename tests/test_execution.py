import json
import os
import signal
import subprocess
import sys
import time

import pytest

from edd_kit.execution import execute
from edd_kit.project import Project
from edd_kit.scaffold import init_project, prepare_change


def project(tmp_path):
    init_project(tmp_path, agent="none")
    prepare_change(tmp_path, "greeting", "Acknowledge a greeting")
    return Project(tmp_path, "greeting")


def configure(app, update):
    data = json.loads(app.contract_path.read_text())
    update(data)
    app.contract_path.write_text(json.dumps(data))
    return Project(app.root, app.change)


def edit_suite(app, old, new):
    source = app.suite_path.read_text()
    assert old in source
    app.suite_path.write_text(source.replace(old, new))


def test_inspect_native_suite_without_application_execution(tmp_path):
    app = project(tmp_path)
    result = execute(app, "inspect")
    assert result["execution_errors"] == []
    assert result["cases"][0]["requirements"] == ["example-acknowledgement"]
    assert result["controls"]
    assert result["controls"][0]["evidence"]["actual_output"]
    assert result["metrics"]["example-acknowledgement"]["requires_paid"] is False
    assert result["gaps"] == []  # Audit can run; human approvals gate acceptance separately.
    assert result["observations"] == []


def test_inspect_rejects_singleton_metric_factory(tmp_path):
    app = project(tmp_path)
    edit_suite(
        app,
        'metrics={"example-acknowledgement": ExampleAcknowledgement}',
        'metrics={"example-acknowledgement": lambda: shared_metric}',
    )
    with app.suite_path.open("a") as stream:
        stream.write("\nshared_metric = ExampleAcknowledgement()\n")
    result = execute(app, "inspect")
    assert result["execution_errors"]
    assert "fresh" in result["execution_errors"][0].lower()


def test_run_real_target_and_grade_with_native_deepeval(tmp_path):
    app = project(tmp_path)
    (tmp_path / "targets/greeting/candidate.py").write_text(
        'import json; print(json.dumps({"actual_output": "Example acknowledged."}))'
    )
    result = execute(app, "run", target="candidate")
    assert result["execution_errors"] == []
    assert len(result["observations"]) == len(result["expected_ids"]) == 1
    row = result["observations"][0]
    assert row["id"] in result["expected_ids"]
    assert row["passed"] is True
    assert row["score"] == 1.0
    assert row["cost_usd"] == 0.0
    assert result["observed_cost_usd"] == 0.0


def test_validation_audit_inverts_negative_control_outcome(tmp_path):
    app = project(tmp_path)
    path = app.directory / "controls.json"
    controls = json.loads(path.read_text())
    for control in controls:
        control["reviewed_by"] = "reviewer"
    path.write_text(json.dumps(controls))
    result = execute(app, "audit")
    assert result["execution_errors"] == []
    assert result["gaps"] == []
    assert all(row["passed"] for row in result["observations"])
    negative = next(row for row in result["observations"] if row["expected_pass"] is False)
    assert negative["observed_passed"] is False


def test_audit_requires_an_independently_authored_negative_control(tmp_path):
    app = project(tmp_path)
    path = app.directory / "controls.json"
    controls = json.loads(path.read_text())
    for control in controls:
        control["independent"] = False
    path.write_text(json.dumps(controls))

    result = execute(Project(app.root, app.change), "audit")

    assert any("independently authored negative" in gap for gap in result["gaps"])


def test_audit_does_not_apply_application_scenario_minimum_to_controls(tmp_path):
    app = project(tmp_path)
    app = configure(app, lambda data: data["requirements"][0].update(min_cases=10))
    inspected = execute(app, "inspect")
    assert any("distinct application cases" in gap for gap in inspected["gaps"])
    audited = execute(app, "audit")
    assert not any("distinct application cases" in gap for gap in audited["gaps"])
    assert audited["gaps"] == inspected["control_gaps"]
    assert inspected["application_gaps"]


def test_raw_run_does_not_inherit_control_review_gaps(tmp_path):
    app = project(tmp_path)
    result = execute(app, "run", target="candidate")
    assert result["control_gaps"] == []
    assert result["application_gaps"] == result["gaps"] == []


def test_calibration_examples_never_enter_validation_audit(tmp_path):
    app = project(tmp_path)
    path = app.directory / "controls.json"
    controls = json.loads(path.read_text())
    controls[0]["partition"] = "calibration"
    controls[0]["reviewed_by"] = "reviewer"
    path.write_text(json.dumps(controls))
    result = execute(app, "audit")
    assert len(result["observations"]) == 1
    assert controls[0]["id"] not in result["expected_ids"][0]
    assert any("positive" in gap for gap in result["gaps"])


def test_preflight_observation_limit_before_any_calls(tmp_path):
    app = project(tmp_path)
    app = configure(app, lambda data: data["profiles"]["acceptance"].update(max_observations=1))
    edit_suite(
        app,
        "self.error = None\n        self.evaluation_cost = 0.0\n        self.score = None",
        "raise AssertionError('Must not grade above preflight budget')",
    )
    result = execute(app, "audit")
    assert result["observations"] == []
    assert "max_observations" in result["execution_errors"][0]


@pytest.mark.parametrize("allow_paid,budget", [(False, 1), (True, 0)])
def test_provider_metric_requires_opt_in_and_positive_budget(tmp_path, allow_paid, budget):
    app = project(tmp_path)
    app = configure(app, lambda data: data["profiles"]["acceptance"].update(max_cost_usd=budget))
    edit_suite(
        app,
        "self.threshold = 1.0",
        'self.threshold = 1.0\n        self.evaluation_model = "synthetic-judge"',
    )
    result = execute(app, "audit", allow_paid=allow_paid)
    assert result["observations"] == []
    assert "--allow-paid" in result["execution_errors"][0]


def test_target_never_receives_expected_answers_or_evaluator_credentials(tmp_path, monkeypatch):
    app = project(tmp_path)
    monkeypatch.setenv("EDD_JUDGE_SECRET", "judge-value")
    monkeypatch.setenv("EDD_TARGET_SECRET", "target-value")
    monkeypatch.setenv("CONFIDENT_API_KEY", "never-cloud")

    def update(data):
        data["evaluator_env"] = ["EDD_JUDGE_SECRET"]
        data["targets"]["candidate"]["env"] = ["EDD_TARGET_SECRET"]

    app = configure(app, update)
    edit_suite(app, "import json", "import json\nimport os")
    edit_suite(
        app,
        "self.error = None\n        self.evaluation_cost = 0.0\n        self.score = None",
        "assert os.environ['EDD_JUDGE_SECRET'] == 'judge-value'\n        "
        "assert 'CONFIDENT_API_KEY' not in os.environ\n        self.error = None\n        "
        "self.evaluation_cost = 0.0\n        self.score = None",
    )
    (app.root / "targets/greeting/candidate.py").write_text(
        "import json, os, sys\nrequest=json.load(sys.stdin)\n"
        "assert set(request) == {'case_id','input','context','fixture','trial'}\n"
        "assert 'expected_output' not in request and 'metadata' not in request\n"
        "assert 'EDD_JUDGE_SECRET' not in os.environ\n"
        "assert 'CONFIDENT_API_KEY' not in os.environ\n"
        "assert os.environ['EDD_TARGET_SECRET']=='target-value'\n"
        'print(json.dumps({"actual_output":"Example acknowledged."}))\n'
    )
    result = execute(app, "run", target="candidate")
    assert result["execution_errors"] == []
    assert result["observations"][0]["passed"] is True


@pytest.mark.parametrize("key", ["fixture", "case_id", "elapsed_seconds"])
def test_target_cannot_overwrite_reserved_evaluator_metadata(tmp_path, key):
    app = project(tmp_path)
    (app.root / "targets/greeting/candidate.py").write_text(
        f'import json; print(json.dumps({{"actual_output":"ok", "metadata":{{{key!r}:"fake"}}}}))'
    )
    result = execute(app, "run", target="candidate")
    assert result["observations"][0]["error"].startswith("target_protocol:")


def test_each_trial_gets_fresh_process_and_each_repetition_fresh_metric(tmp_path):
    app = project(tmp_path)
    app = configure(
        app, lambda data: data["profiles"]["acceptance"].update(trials=2, grader_repetitions=2)
    )
    edit_suite(app, "self.threshold = 1.0", "self.threshold = 1.0\n        self.calls = 0")
    edit_suite(
        app,
        "self.score = float(test_case.actual_output == test_case.expected_output)",
        "self.calls += 1\n        self.score = float(self.calls == 1)",
    )
    (app.root / "targets/greeting/candidate.py").write_text(
        'import json,os; print(json.dumps({"actual_output": str(os.getpid())}))'
    )
    result = execute(app, "run", target="candidate")
    rows = result["observations"]
    assert len(rows) == 4 and all(row["passed"] for row in rows)
    assert rows[0]["actual_output"] == rows[1]["actual_output"]
    assert rows[2]["actual_output"] == rows[3]["actual_output"]
    assert rows[0]["actual_output"] != rows[2]["actual_output"]


def test_unknown_grader_cost_stops_further_calls(tmp_path):
    app = project(tmp_path)
    edit_suite(app, "self.evaluation_cost = 0.0", "self.evaluation_cost = None")
    result = execute(app, "audit")
    assert len(result["observations"]) == 1
    assert any("unknown cost" in gap for gap in result["gaps"])


def test_observed_cost_cap_stops_scheduling_without_claiming_hard_cap(tmp_path):
    app = project(tmp_path)
    app = configure(app, lambda data: data["profiles"]["acceptance"].update(max_cost_usd=0.1))
    edit_suite(app, "self.evaluation_cost = 0.0", "self.evaluation_cost = 0.2")
    result = execute(app, "audit", allow_paid=True)
    assert len(result["observations"]) == 1
    assert result["observed_cost_usd"] == 0.2
    assert any("cost budget" in gap for gap in result["gaps"])


def test_completed_observations_survive_whole_operation_timeout(tmp_path):
    app = project(tmp_path)
    app = configure(
        app,
        lambda data: data["profiles"]["acceptance"].update(timeout_seconds=2, grader_repetitions=2),
    )
    edit_suite(app, "import json", "import json\nimport time\nMEASUREMENTS = 0")
    edit_suite(
        app,
        "def measure(self, test_case, *args, **kwargs):",
        "def measure(self, test_case, *args, **kwargs):\n        global MEASUREMENTS\n        "
        "MEASUREMENTS += 1\n        if MEASUREMENTS == 2: time.sleep(30)",
    )
    result = execute(app, "audit")
    assert len(result["expected_ids"]) == 4
    assert len(result["observations"]) == 1
    assert "deadline" in result["execution_errors"][0]


def test_local_grader_imports_must_be_declared_artifacts(tmp_path):
    app = project(tmp_path)
    (app.root / "helper.py").write_text("VALUE = 1\n")
    edit_suite(
        app,
        "import json",
        f"import json\nimport sys\nsys.path.insert(0, {str(app.root)!r})\nimport helper",
    )
    result = execute(app, "inspect")
    assert "outside the declared bundle" in result["execution_errors"][0]
    app = configure(app, lambda data: data["artifacts"].append("helper.py"))
    assert execute(app, "inspect")["execution_errors"] == []


def test_lazy_project_import_cannot_escape_fingerprinted_bundle(tmp_path):
    app = project(tmp_path)
    (app.root / "helper.py").write_text("VALUE = 1\n")
    edit_suite(
        app, "import json", f"import json\nimport sys\nsys.path.insert(0, {str(app.root)!r})"
    )
    edit_suite(
        app,
        "def measure(self, test_case, *args, **kwargs):",
        "def measure(self, test_case, *args, **kwargs):\n        import helper",
    )
    result = execute(app, "audit")
    assert "outside the declared bundle" in result["execution_errors"][0]
    assert result["observations"] == []


def test_application_cases_cannot_replay_control_actual_outputs(tmp_path):
    app = project(tmp_path)
    edit_suite(
        app,
        'LLMTestCase(input=row["input"], expected_output=row["expected_output"])',
        'LLMTestCase(input=row["input"], expected_output=row["expected_output"], '
        "actual_output='canned')",
    )
    result = execute(app, "inspect")
    assert "without saved actual_output" in result["execution_errors"][0]


def test_suite_prints_and_exceptions_do_not_leak_into_evidence(tmp_path):
    app = project(tmp_path)
    edit_suite(
        app,
        "def build_suite():",
        "def build_suite():\n    print('synthetic-secret')\n"
        "    raise ValueError('synthetic-secret')",
    )
    result = execute(app, "inspect")
    assert result["execution_errors"]
    assert "synthetic-secret" not in json.dumps(result)


def test_suite_project_errors_cannot_leak_secret_messages(tmp_path):
    app = project(tmp_path)
    edit_suite(
        app,
        "def build_suite():",
        "def build_suite():\n    from edd_kit.project import ProjectError\n"
        "    raise ProjectError('synthetic-secret')",
    )
    result = execute(app, "inspect")
    assert result["execution_errors"]
    assert "synthetic-secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("retrieval_context", "['saved retrieval']"),
        ("tools_called", "[]"),
        ("completion_time", "0.01"),
        ("token_cost", "0.0"),
    ],
)
def test_cases_cannot_substitute_saved_application_observations(tmp_path, field, value):
    app = project(tmp_path)
    edit_suite(
        app,
        'LLMTestCase(input=row["input"], expected_output=row["expected_output"])',
        f'LLMTestCase(input=row["input"], expected_output=row["expected_output"], {field}={value})',
    )
    result = execute(app, "inspect")
    assert any("saved observed fields" in error for error in result["execution_errors"])


def test_metric_factory_configuration_must_match_preflight_before_grading(tmp_path):
    app = project(tmp_path)
    edit_suite(app, "import json", "import json\nCONSTRUCTIONS = 0")
    edit_suite(
        app,
        "self.threshold = 1.0",
        "global CONSTRUCTIONS\n        CONSTRUCTIONS += 1\n"
        "        self.threshold = 1.0 if CONSTRUCTIONS == 1 else 0.5",
    )
    result = execute(app, "audit")
    assert result["observations"][0]["error"]
    assert result["observations"][0]["passed"] is None


def test_failed_grader_with_unknown_cost_does_not_schedule_more_calls(tmp_path):
    app = project(tmp_path)
    edit_suite(
        app,
        "def measure(self, test_case, *args, **kwargs):",
        "def measure(self, test_case, *args, **kwargs):\n        raise ValueError('failure')",
    )
    result = execute(app, "audit")
    assert len(result["observations"]) == 1
    assert result["observations"][0]["error"]
    assert any("unknown cost" in gap for gap in result["gaps"])


@pytest.mark.parametrize(
    "raw",
    [
        '{"type":"complete","type":"complete","data":{"execution_errors":[]}}\n',
        '{"type":"complete","data":{"observed_cost_usd":NaN}}\n',
        '{"type":"complete","data":{"observed_cost_usd":1e999}}\n',
        '{"type":"plan","data":{"observations":[]}}\n',
    ],
)
def test_parent_rejects_malformed_worker_protocol_without_logging_it(tmp_path, raw):
    app = project(tmp_path)
    edit_suite(app, "import json", f"import json\nimport os\nos.write(1, {raw.encode()!r})")
    result = execute(app, "inspect")
    assert any("invalid protocol" in error for error in result["execution_errors"])


def test_parent_bounds_worker_output(tmp_path):
    app = project(tmp_path)
    edit_suite(app, "import json", "import json\nimport os\nos.write(1, b'x' * (33 * 1024 * 1024))")
    result = execute(app, "inspect")
    assert any("32 MiB" in error for error in result["execution_errors"])


def test_operation_timeout_cleans_application_descendants(tmp_path):
    app = project(tmp_path)
    app = configure(app, lambda data: data["profiles"]["acceptance"].update(timeout_seconds=2))
    marker = app.root / "target-child.pid"
    (app.root / "targets/greeting/candidate.py").write_text(
        "import subprocess,sys,time\nfrom pathlib import Path\n"
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
        f"Path({str(marker)!r}).write_text(str(child.pid))\ntime.sleep(30)\n"
    )
    result = execute(app, "run", target="candidate")
    assert any("deadline" in error for error in result["execution_errors"])
    assert marker.exists(), "Target must start before testing descendant cleanup"
    child_pid = int(marker.read_text())
    # Reaping an orphan may lag slightly; the OS must not leave it running.
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        pytest.fail("Application child survived evaluator timeout")


def test_sigterm_on_execution_caller_unwinds_worker_and_target(tmp_path):
    app = project(tmp_path)
    marker = app.root / "target.pid"
    (app.root / "targets/greeting/candidate.py").write_text(
        "import os,time\nfrom pathlib import Path\n"
        f"Path({str(marker)!r}).write_text(str(os.getpid()))\ntime.sleep(30)"
    )
    caller = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "from pathlib import Path; from edd_kit.project import Project; "
            "from edd_kit.execution import execute; "
            f"execute(Project(Path({str(app.root)!r}), 'greeting'),'run',target='candidate')",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        caller.send_signal(signal.SIGTERM)
        caller.wait(timeout=5)
        child_pid = int(marker.read_text())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        else:
            pytest.fail("Target survived execution caller SIGTERM")
    finally:
        if caller.poll() is None:
            caller.kill()
            caller.wait()
