"""Target protocol tests exercise real processes through the public interface."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from edd_kit.target import TargetError, invoke_target


def test_target_receives_request_and_returns_application_output(tmp_path):
    result = invoke_target(
        [
            sys.executable,
            "-c",
            "import json,sys; request=json.load(sys.stdin); "
            "print(json.dumps({'actual_output': request['input'].upper()}))",
        ],
        {"case_id": "greeting", "input": "hello", "trial": 1},
        cwd=tmp_path,
        env_names=[],
        timeout_seconds=3,
    )

    assert result == {"actual_output": "HELLO"}


@pytest.mark.parametrize(
    "output",
    [
        "[]",
        "{}",
        '{"actual_output": 12}',
        '{"actual_output": "ok", "passed": true}',
        '{"actual_output": "ok", "context": {"untrusted": "shape"}}',
        '{"actual_output": "ok", "retrieval_context": [12]}',
        '{"actual_output": "ok", "tools_called": ["cancel"]}',
        '{"actual_output": "ok", "metadata": []}',
        '{"actual_output": "ok", "metadata": {"score": NaN}}',
        '{"actual_output": "first", "actual_output": "second"}',
        'prefix {"actual_output": "ok"}',
    ],
)
def test_target_rejects_invalid_response_protocol(tmp_path, output):
    with pytest.raises(TargetError) as caught:
        invoke_target(
            [sys.executable, "-c", "import sys; sys.stdout.write(sys.argv[1])", output],
            {"input": "hello"},
            cwd=tmp_path,
            env_names=[],
            timeout_seconds=3,
        )

    assert caught.value.code == "protocol"


@pytest.mark.parametrize(
    "target_request",
    [
        {"input": "hello", "expected_output": "secret answer"},
        {"input": "hello", "expected_tools": ["cancel"]},
        {"input": "hello", "grader": "private"},
        {"input": 4},
        {"input": "hello", "context": "unsupported"},
        {"input": "hello", "fixture": []},
        {"input": "hello", "metadata": {"value": float("nan")}},
    ],
)
def test_target_rejects_requests_that_leak_expected_outcomes_or_break_protocol(
    tmp_path, target_request
):
    with pytest.raises(TargetError) as caught:
        invoke_target(
            [sys.executable, "-c", "raise SystemExit(93)"],
            target_request,
            cwd=tmp_path,
            env_names=[],
            timeout_seconds=3,
        )

    assert caught.value.code == "configuration"


def test_target_inherits_only_requested_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("EDD_JUDGE_SECRET", "must-not-leak")
    monkeypatch.setenv("EDD_TARGET_SECRET", "target-only")
    result = invoke_target(
        [
            sys.executable,
            "-c",
            "import json,os; print(json.dumps({'actual_output': "
            "json.dumps(sorted(k for k in os.environ if k.startswith('EDD_')))}))",
        ],
        {"input": "hello"},
        cwd=tmp_path,
        env_names=["EDD_TARGET_SECRET"],
        timeout_seconds=3,
    )

    assert json.loads(result["actual_output"]) == ["EDD_TARGET_SECRET"]


def test_target_refuses_a_missing_explicit_environment_variable(tmp_path, monkeypatch):
    monkeypatch.delenv("EDD_TARGET_MISSING", raising=False)
    with pytest.raises(TargetError) as caught:
        invoke_target(
            [sys.executable, "-c", "raise SystemExit(93)"],
            {"input": "hello"},
            cwd=tmp_path,
            env_names=["EDD_TARGET_MISSING"],
            timeout_seconds=3,
        )

    assert caught.value.code == "configuration"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_target_rejects_invalid_execution_limits(tmp_path, timeout):
    with pytest.raises(TargetError) as caught:
        invoke_target(
            [sys.executable, "-c", "raise SystemExit(93)"],
            {"input": "hello"},
            cwd=tmp_path,
            env_names=[],
            timeout_seconds=timeout,
        )

    assert caught.value.code == "configuration"


def test_target_reports_spawn_failure_without_command_contents(tmp_path):
    with pytest.raises(TargetError) as caught:
        invoke_target(
            [str(tmp_path / "absent-target"), "credential-must-not-leak"],
            {"input": "hello"},
            cwd=tmp_path,
            env_names=[],
            timeout_seconds=3,
        )

    assert caught.value.code == "spawn"
    assert "credential-must-not-leak" not in str(caught.value)


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_unbounded_target_output_is_stopped_without_logging_contents(tmp_path, stream):
    with pytest.raises(TargetError) as caught:
        invoke_target(
            [sys.executable, "-c", f"import sys; sys.{stream}.write('private-output' * 10000)"],
            {"input": "hello"},
            cwd=tmp_path,
            env_names=[],
            timeout_seconds=3,
            max_output_bytes=128,
        )

    assert caught.value.code == "output_limit"
    assert "private-output" not in str(caught.value)


@pytest.mark.parametrize("outcome", ["success", "timeout"])
def test_target_descendants_are_cleaned_up_after_success_or_timeout(tmp_path, outcome):
    marker = tmp_path / "leaked-descendant"
    descendant = f"import time,pathlib; time.sleep(0.4); pathlib.Path({str(marker)!r}).touch()"
    target = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {descendant!r}], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        + ('print(\'{"actual_output":"ok"}\')' if outcome == "success" else "time.sleep(20)")
    )
    if outcome == "success":
        assert invoke_target(
            [sys.executable, "-c", target],
            {"input": "hello"},
            cwd=tmp_path,
            env_names=[],
            timeout_seconds=3,
        ) == {"actual_output": "ok"}
    else:
        with pytest.raises(TargetError) as caught:
            invoke_target(
                [sys.executable, "-c", target],
                {"input": "hello"},
                cwd=tmp_path,
                env_names=[],
                timeout_seconds=0.15,
            )
        assert caught.value.code == "timeout"
    time.sleep(0.5)
    assert not marker.exists()


def test_worker_sigterm_handler_allows_target_cleanup(tmp_path):
    marker = tmp_path / "leaked-after-cancellation"
    descendant = f"import time,pathlib; time.sleep(0.5); pathlib.Path({str(marker)!r}).touch()"
    target = (
        "import subprocess,sys,os,signal,time; "
        f"subprocess.Popen([sys.executable, '-c', {descendant!r}]); "
        "time.sleep(0.05); os.kill(os.getppid(), signal.SIGTERM); time.sleep(20)"
    )
    wrapper = (
        "import signal,sys; from pathlib import Path; from edd_kit.target import invoke_target\n"
        "def interrupted(signum, frame): raise KeyboardInterrupt\n"
        "signal.signal(signal.SIGTERM, interrupted)\n"
        "try:\n"
        f" invoke_target([sys.executable, '-c', {target!r}], {{'input':'hello'}}, "
        f"cwd=Path({str(tmp_path)!r}), env_names=[], timeout_seconds=10)\n"
        "except KeyboardInterrupt: sys.exit(42)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", wrapper],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=3,
    )
    assert result.returncode == 42
    time.sleep(0.6)
    assert not marker.exists()


def test_target_disables_implicit_dotenv_and_telemetry_configuration(tmp_path):
    result = invoke_target(
        [
            sys.executable,
            "-c",
            "import os,json; print(json.dumps({'actual_output':'ok', 'metadata': "
            "{k:os.getenv(k) for k in ['DEEPEVAL_DISABLE_DOTENV','DEEPEVAL_TELEMETRY_OPT_OUT']}}))",
        ],
        {"input": "hello"},
        cwd=tmp_path,
        env_names=[],
        timeout_seconds=3,
    )

    assert result["metadata"] == {"DEEPEVAL_DISABLE_DOTENV": "1", "DEEPEVAL_TELEMETRY_OPT_OUT": "1"}
