from edd_kit.scaffold import init_project, prepare_change


def test_generated_pipeline_carries_hashed_evaluator_dependencies(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "feature", "A feature", "starter")
    lock = tmp_path / "evals/feature/eval-requirements.lock"
    assert lock.is_file()
    text = lock.read_text()
    assert "deepeval==4.2.3" in text
    assert "--hash=sha256:" in text
    assert "-e ." not in text
