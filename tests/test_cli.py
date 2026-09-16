import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def command(root: Path, *arguments):
    return subprocess.run(
        [sys.executable, "-m", "edd_kit", "--root", str(root), *arguments],
        text=True,
        capture_output=True,
        timeout=30,
        env={**os.environ, "DEEPEVAL_DISABLE_DOTENV": "1", "DEEPEVAL_TELEMETRY_OPT_OUT": "1"},
    )


def test_cli_initializes_and_prepares_without_claiming_domain_evaluation_is_ready(tmp_path):
    initialized = command(tmp_path, "init", "--agent", "none", "--json")
    assert initialized.returncode == 0, initialized.stderr
    initialization = json.loads(initialized.stdout)
    assert initialization["environment"]["decision"] == "PASS"
    assert initialization["restart_required"] is False
    prepared = command(
        tmp_path, "prepare", "answering", "--brief", "Answer questions from documents", "--json"
    )
    assert prepared.returncode == 0, prepared.stderr
    output = json.loads(prepared.stdout)
    assert output["authoring_required"] is True
    assert output["change"] == "answering"
    status = command(tmp_path, "status", "answering", "--acceptance", "--json")
    assert status.returncode == 0
    assert json.loads(status.stdout)["ready_to_build"] is False


def test_cli_errors_are_machine_readable_and_nonzero(tmp_path):
    result = command(tmp_path, "verify", "missing", "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["decision"] == "ERROR"


def test_cli_help_explains_terminal_scaffolding_and_agent_authoring(tmp_path):
    result = command(tmp_path, "--help")
    assert result.returncode == 0
    assert "prepare" in result.stdout and "verify" in result.stdout


@pytest.mark.parametrize(
    "config", ["schema_version = 1\n", "schema_version = 1\nchanges_dir = 7\n"]
)
def test_status_without_change_rejects_invalid_configuration_as_json(tmp_path, config):
    (tmp_path / "edd.toml").write_text(config)
    result = command(tmp_path, "status", "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["decision"] == "ERROR"
    assert "Traceback" not in result.stderr


def test_cli_init_rejects_symlinked_root_without_touching_the_destination(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    result = command(linked, "init", "--agent", "none", "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["decision"] == "ERROR"
    assert list(outside.iterdir()) == []


def test_human_inspection_is_labelled_configuration_only(tmp_path):
    assert command(tmp_path, "init", "--agent", "none").returncode == 0
    assert command(tmp_path, "prepare", "feature", "--brief", "A draft").returncode == 0
    inspected = command(tmp_path, "inspect", "feature")
    assert inspected.returncode == 0
    assert "Configuration only" in inspected.stdout
    assert "not grader validation or feature acceptance" in inspected.stdout


def test_status_presents_workflow_phase_and_additive_machine_actions(tmp_path):
    assert command(tmp_path, "init", "--agent", "none").returncode == 0
    assert (
        command(tmp_path, "prepare", "feature", "--brief", "A reviewable behavior").returncode == 0
    )

    human = command(tmp_path, "status", "feature", "--acceptance")
    assert human.returncode == 0
    assert "EDD feature — PREPARE" in human.stdout
    assert "Next (cli)" in human.stdout
    assert "edd review feature --write" in human.stdout
    assert "EDD feature: INCONCLUSIVE" not in human.stdout

    machine = command(tmp_path, "status", "feature", "--acceptance", "--json")
    payload = json.loads(machine.stdout)
    assert payload["decision"] == "INCONCLUSIVE"
    assert payload["workflow"]["phase"] == "prepare"
    assert payload["actions"][0]["id"] == "write-review-packet"
    assert payload["diagnostics"][0]["code"] == "review-packet-missing"

    dashboard = command(tmp_path, "status")
    assert "MEASURE" in dashboard.stdout
    assert "Next: edd measure feature --target TARGET" in dashboard.stdout


def test_review_packet_is_read_only_and_records_two_explicit_review_areas(tmp_path):
    assert command(tmp_path, "init", "--agent", "none").returncode == 0
    assert command(tmp_path, "prepare", "feature", "--brief", "A behavior").returncode == 0
    control_path = tmp_path / "evals" / "feature" / "controls.json"
    before = control_path.read_bytes()

    preview = command(tmp_path, "review", "feature", "--json")
    assert preview.returncode == 0, preview.stdout
    packet = json.loads(preview.stdout)
    assert packet["kind"] == "review-packet"
    assert packet["controls"][0]["evidence"]["actual_output"]
    human = command(tmp_path, "review", "feature")
    assert "## Domain expectations" in human.stdout
    assert "## Technical validation" in human.stdout
    assert control_path.read_bytes() == before
    assert not (tmp_path / "evals" / "feature" / "review.json").exists()

    written = command(tmp_path, "review", "feature", "--write", "--json")
    assert written.returncode == 0
    assert (tmp_path / "evals" / "feature" / "REVIEW.md").is_file()

    approved = command(
        tmp_path,
        "review",
        "feature",
        "--area",
        "domain",
        "--decision",
        "approve",
        "--by",
        "Product owner",
        "--note",
        "Reviewed the current examples",
        "--criteria-digest",
        packet["criteria_digest"],
        "--json",
    )
    assert approved.returncode == 0, approved.stdout
    assert json.loads(approved.stdout)["review"]["domain"]["status"] == "approved"
    assert command(tmp_path, "audit", "feature").returncode == 0
    technical = command(
        tmp_path,
        "review",
        "feature",
        "--area",
        "technical",
        "--decision",
        "approve",
        "--by",
        "Evaluation engineer",
        "--note",
        "The audit and controls measure the reviewed rule",
        "--criteria-digest",
        packet["criteria_digest"],
        "--json",
    )
    assert technical.returncode == 0, technical.stdout
    assert control_path.read_bytes() == before
    status = json.loads(command(tmp_path, "status", "feature", "--acceptance", "--json").stdout)
    assert status["review"]["status"] == "current"


def test_review_rejects_stale_digest_without_changing_controls(tmp_path):
    assert command(tmp_path, "init", "--agent", "none").returncode == 0
    assert command(tmp_path, "prepare", "feature", "--brief", "A behavior").returncode == 0
    assert command(tmp_path, "review", "feature", "--write").returncode == 0
    control_path = tmp_path / "evals" / "feature" / "controls.json"
    before = control_path.read_bytes()
    result = command(
        tmp_path,
        "review",
        "feature",
        "--area",
        "domain",
        "--decision",
        "approve",
        "--by",
        "Reviewer",
        "--note",
        "Reviewed",
        "--criteria-digest",
        "0" * 64,
        "--json",
    )
    assert result.returncode == 2
    assert "Criteria changed" in json.loads(result.stdout)["error"]
    assert control_path.read_bytes() == before


def test_legacy_control_approval_flags_return_migration_guidance(tmp_path):
    assert command(tmp_path, "init", "--agent", "none").returncode == 0
    assert command(tmp_path, "prepare", "feature", "--brief", "A behavior").returncode == 0

    result = command(
        tmp_path,
        "review",
        "feature",
        "--by",
        "Reviewer",
        "--note",
        "Old flow",
        "--approve-controls",
        "all",
        "--json",
    )

    assert result.returncode == 2
    assert "--area technical --decision approve" in json.loads(result.stdout)["error"]


def test_run_infers_only_unambiguous_application_target(tmp_path):
    assert command(tmp_path, "init", "--agent", "none").returncode == 0
    assert command(tmp_path, "prepare", "feature", "--brief", "A behavior").returncode == 0
    inferred = command(tmp_path, "run", "feature", "--json")
    assert json.loads(inferred.stdout)["target"] == "candidate"

    other = tmp_path / "other"
    assert command(other, "init", "--agent", "none").returncode == 0
    assert (
        command(
            other,
            "prepare",
            "orders",
            "--brief",
            "Cancel orders",
            "--template",
            "cancellation",
        ).returncode
        == 0
    )
    ambiguous = command(other, "run", "orders", "--json")
    assert ambiguous.returncode == 2
    assert (
        "eligible candidate targets: candidate, noop, wrong-owner"
        in json.loads(ambiguous.stdout)["error"]
    )


def test_demo_is_isolated_and_detects_both_seeded_defects(tmp_path):
    before = list(tmp_path.iterdir())
    result = command(tmp_path, "demo", "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["demonstrated"] is True
    assert payload["checks"]["fabricated_success"] == "DETECTED"
    assert payload["checks"]["wrong_owner_change"] == "DETECTED"
    assert list(tmp_path.iterdir()) == before


def test_unknown_change_suggests_near_match(tmp_path):
    assert command(tmp_path, "init", "--agent", "none").returncode == 0
    assert command(tmp_path, "prepare", "answering", "--brief", "Answer").returncode == 0
    result = command(tmp_path, "status", "ansering", "--json")
    assert result.returncode == 2
    assert "Did you mean: answering?" in json.loads(result.stdout)["error"]
