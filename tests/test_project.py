import json

import pytest

from edd_kit.project import Project, ProjectError


def make_project(tmp_path):
    (tmp_path / "edd.toml").write_text('schema_version = 1\nchanges_dir = "evals"\n')
    change = tmp_path / "evals" / "orders"
    change.mkdir(parents=True)
    (change / "suite.py").write_text("def build_suite(): pass\n")
    (tmp_path / "app.py").write_text("print('not implemented')\n")
    (change / "contract.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "change": "orders",
                "title": "Orders",
                "requirements": [{"id": "correct", "description": "Correct result"}],
                "profiles": {"dev": {}, "acceptance": {}},
                "targets": {
                    "candidate": {
                        "kind": "application",
                        "command": ["python3", "app.py"],
                        "files": ["app.py"],
                    }
                },
            }
        )
    )
    return change


def test_criteria_changes_invalidate_bundle_but_target_changes_do_not(tmp_path):
    change = make_project(tmp_path)
    project = Project(tmp_path, "orders")
    before = project.bundle_digest()
    target = project.target_digest("candidate")
    (tmp_path / "app.py").write_text("print('implemented')\n")
    assert project.bundle_digest() == before
    assert project.target_digest("candidate") != target
    (change / "rubric.md").write_text("Reject fabricated confirmation.\n")
    assert project.bundle_digest() != before


def test_project_rejects_traversal_and_symlinked_criteria(tmp_path):
    change = make_project(tmp_path)
    with pytest.raises(ProjectError):
        Project(tmp_path, "../../outside")
    (change / "leak").symlink_to(tmp_path / "app.py")
    with pytest.raises(ProjectError, match="symlink"):
        Project(tmp_path, "orders").bundle_digest()


def test_project_rejects_symlinked_root(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    make_project(actual)
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ProjectError, match="symlink"):
        Project(linked, "orders")


def test_relative_target_executable_is_identified_from_project_cwd(tmp_path):
    change = make_project(tmp_path)
    runner = tmp_path / "runner"
    runner.write_text("#!/bin/sh\nprintf 'target response'\n")
    runner.chmod(0o755)
    contract = json.loads((change / "contract.json").read_text())
    contract["targets"]["candidate"].update(command=["./runner"], files=["runner"])
    (change / "contract.json").write_text(json.dumps(contract))
    identity = Project(tmp_path, "orders").target_identity("candidate")
    assert identity["executable"] == str(runner)


def test_target_runtime_replacement_changes_identity_even_at_same_path(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    change = make_project(root)
    runtime = tmp_path / "external-runtime"
    runtime.write_text("#!/bin/sh\nprintf first\n")
    runtime.chmod(0o755)
    contract = json.loads((change / "contract.json").read_text())
    contract["targets"]["candidate"]["command"] = [str(runtime), "app.py"]
    (change / "contract.json").write_text(json.dumps(contract))
    project = Project(root, "orders")
    before = project.target_digest("candidate")
    runtime.write_text("#!/bin/sh\nprintf second\n")
    assert project.target_digest("candidate") != before


def test_target_command_cannot_execute_an_unfingerprinted_local_script(tmp_path):
    change = make_project(tmp_path)
    (tmp_path / "unrelated.txt").write_text("Only this file is fingerprinted")
    contract = json.loads((change / "contract.json").read_text())
    contract["targets"]["candidate"]["files"] = ["unrelated.txt"]
    (change / "contract.json").write_text(json.dumps(contract))
    with pytest.raises(ProjectError, match="target.files"):
        Project(tmp_path, "orders").target_identity("candidate")


def test_target_code_cannot_also_be_an_external_evaluation_artifact(tmp_path):
    change = make_project(tmp_path)
    contract = json.loads((change / "contract.json").read_text())
    contract["artifacts"] = ["app.py"]
    (change / "contract.json").write_text(json.dumps(contract))
    with pytest.raises(ProjectError, match="separate"):
        Project(tmp_path, "orders").target_identity("candidate")


def test_inline_target_code_is_not_mistaken_for_a_file_argument(tmp_path):
    change = make_project(tmp_path)
    contract = json.loads((change / "contract.json").read_text())
    contract["targets"]["candidate"]["command"] = ["python3", "-c", "#" + "x" * 1024]
    (change / "contract.json").write_text(json.dumps(contract))
    assert Project(tmp_path, "orders").target_identity("candidate")["executable_sha256"]
