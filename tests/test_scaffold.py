import json
import runpy
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from edd_kit.scaffold import init_project, prepare_change, sync_skills


def test_init_is_idempotent_and_preserves_existing_project_files(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("user-private/\n")
    (tmp_path / "application.py").write_text("print('existing application')\n")

    first = init_project(tmp_path, agent="none")
    config = (tmp_path / "edd.toml").read_text()
    second = init_project(tmp_path, agent="none")

    assert "edd.toml" in first["created"]
    assert second["created"] == []
    assert (tmp_path / "edd.toml").read_text() == config
    assert (tmp_path / ".gitignore").read_text() == "user-private/\n"
    assert (tmp_path / "application.py").read_text() == "print('existing application')\n"
    assert (tmp_path / ".edd" / ".gitignore").is_file()


def test_init_rejects_symlinked_managed_directory_before_writing(tmp_path: Path):
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (project / ".edd").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        init_project(project, agent="none")

    assert not (project / "edd.toml").exists()
    assert list(outside.iterdir()) == []


def test_prepare_creates_an_explicit_unreviewed_starter_without_replacing_it(tmp_path: Path):
    init_project(tmp_path, agent="none")
    result = prepare_change(tmp_path, "answer-support", "Answer support questions accurately.")
    feature = tmp_path / "evals" / "answer-support"
    contract = json.loads((feature / "contract.json").read_text())

    assert result["change"] == "answer-support"
    assert contract["change"] == "answer-support"
    assert contract["suite"] == "suite.py:build_suite"
    assert "Answer support questions accurately." in (feature / "brief.md").read_text()
    assert all(
        control["reviewed_by"] is None
        for control in json.loads((feature / "controls.json").read_text())
    )
    assert (feature / "suite.py").is_file()
    assert (feature / "cases.json").is_file()
    assert (tmp_path / "targets" / "answer-support" / "candidate.py").is_file()
    assert not (feature / "target.py").exists()
    (feature / "brief.md").write_text("User-authored acceptance intent.\n")
    with pytest.raises(ValueError, match="already exists"):
        prepare_change(tmp_path, "answer-support", "Replacement brief")
    assert (feature / "brief.md").read_text() == "User-authored acceptance intent.\n"


def test_packaged_skill_sync_previews_and_preserves_user_edits(tmp_path: Path):
    init_project(tmp_path, agent="codex")
    prepare_skill = tmp_path / ".agents" / "skills" / "edd-prepare" / "SKILL.md"
    check_skill = tmp_path / ".agents" / "skills" / "edd-check" / "SKILL.md"
    assert "DeepEval" in prepare_skill.read_text()
    prepare_skill.write_text("Local team instructions.\n")
    check_skill.unlink()

    preview = sync_skills(tmp_path, agent="codex")
    assert preview["preview"] is True
    assert ".agents/skills/edd-prepare/SKILL.md" in preview["conflicts"]
    assert ".agents/skills/edd-check/SKILL.md" in preview["created"]
    assert not check_skill.exists()

    applied = sync_skills(tmp_path, agent="codex", preview=False)
    assert applied["conflicts"] == preview["conflicts"]
    assert prepare_skill.read_text() == "Local team instructions.\n"
    assert check_skill.is_file()
    assert init_project(tmp_path, agent="codex")["created"] == []


def test_cancellation_demo_executes_native_metrics_and_catches_false_success(tmp_path: Path):
    init_project(tmp_path, agent="none")
    prepare_change(
        tmp_path, "cancel-order", "Cancel eligible owned orders.", template="cancellation"
    )
    directory = tmp_path / "evals" / "cancel-order"
    suite = runpy.run_path(str(directory / "suite.py"))["build_suite"]()

    for control in suite.controls:
        metric = suite.metrics[control.requirement_id]()
        metric.measure(control.test_case)
        assert metric.is_successful() is control.expected_pass

    def observed_case(case, target):
        response = subprocess.run(
            [sys.executable, str(tmp_path / "targets" / "cancel-order" / f"{target}.py")],
            input=json.dumps({"input": case.test_case.input, "fixture": case.fixture}),
            capture_output=True,
            text=True,
            check=True,
        )
        output = json.loads(response.stdout)
        return case.test_case.model_copy(
            update={
                "actual_output": output["actual_output"],
                "metadata": {
                    **case.test_case.metadata,
                    "fixture": case.fixture,
                    **output["metadata"],
                },
            }
        )

    for case in suite.cases:
        observed = observed_case(case, "candidate")
        for requirement in case.requirements:
            metric = suite.metrics[requirement]()
            metric.measure(observed)
            assert metric.is_successful(), (case.case_id, requirement, metric.reason)

    forged = observed_case(suite.cases[0], "noop")
    outcome = suite.metrics["correct-order-state"]()
    outcome.measure(forged)
    assert forged.actual_output == "Order cancelled."
    assert not outcome.is_successful()

    unauthorized = observed_case(suite.cases[1], "wrong-owner")
    ownership = suite.metrics["preserve-other-customers-orders"]()
    ownership.measure(unauthorized)
    assert not ownership.is_successful()


@pytest.mark.parametrize(
    "change", ["../escape", "/absolute", "nested/change", "1invalid", "a" * 65]
)
def test_prepare_rejects_invalid_change_identifiers_before_writing(tmp_path: Path, change: str):
    init_project(tmp_path, agent="none")
    with pytest.raises(ValueError, match="change"):
        prepare_change(tmp_path, change, "A feature")
    assert not (tmp_path / "evals").exists()
    assert not (tmp_path / "targets").exists()


@pytest.mark.parametrize("template", ["starter", "cancellation"])
def test_offline_template_metrics_report_known_zero_cost(tmp_path: Path, template: str):
    init_project(tmp_path, agent="none")
    prepare_change(tmp_path, "offline", "An offline example.", template=template)
    suite = runpy.run_path(str(tmp_path / "evals" / "offline" / "suite.py"))["build_suite"]()
    for control in suite.controls:
        metric = suite.metrics[control.requirement_id]()
        metric.evaluation_cost = None  # The worker clears stale metric results before measurement.
        metric.measure(control.test_case)
        assert metric.evaluation_cost == 0.0


def test_prepare_honors_configured_relative_changes_directory(tmp_path: Path):
    init_project(tmp_path, agent="none")
    (tmp_path / "edd.toml").write_text('schema_version = 1\nchanges_dir = "quality/evals"\n')
    prepare_change(tmp_path, "support_answer", "Answer support questions.")
    assert (tmp_path / "quality" / "evals" / "support_answer" / "contract.json").is_file()
    assert not (tmp_path / "evals").exists()


@pytest.mark.parametrize("changes_dir", ["../outside", "/absolute", ".git/hooks", ""])
def test_prepare_rejects_unsafe_changes_directory_before_writing(tmp_path: Path, changes_dir: str):
    init_project(tmp_path, agent="none")
    (tmp_path / "edd.toml").write_text(f'schema_version = 1\nchanges_dir = "{changes_dir}"\n')
    with pytest.raises(ValueError, match="changes_dir"):
        prepare_change(tmp_path, "support", "Answer support questions.")
    assert not (tmp_path / "evals").exists()
    assert not (tmp_path / "targets").exists()


@pytest.mark.parametrize("directory", ["evals", "targets"])
def test_prepare_rejects_symlinked_destination_without_partial_scaffold(
    tmp_path: Path, directory: str
):
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    outside.mkdir()
    init_project(project, agent="none")
    (project / directory).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        prepare_change(project, "support", "Answer support questions.")
    assert list(outside.iterdir()) == []
    other = "targets" if directory == "evals" else "evals"
    assert not (project / other).exists()


def test_skill_sync_updates_only_known_unedited_installed_version(tmp_path: Path):
    init_project(tmp_path, agent="claude")
    relative = ".claude/skills/edd-prepare/SKILL.md"
    path = tmp_path / relative
    packaged_content = path.read_bytes()
    old_content = b"An older EDD-distributed version.\n"
    path.write_bytes(old_content)
    manifest_path = tmp_path / ".edd" / "skills.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][relative] = sha256(old_content).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    preview = sync_skills(tmp_path, agent="claude")
    assert preview["updated"] == [relative]
    assert path.read_bytes() == old_content
    applied = sync_skills(tmp_path, agent="claude", preview=False)
    assert applied["updated"] == [relative]
    assert path.read_bytes() == packaged_content
    assert sync_skills(tmp_path, agent="claude")["updated"] == []
