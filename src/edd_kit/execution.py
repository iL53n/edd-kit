"""Bounded evaluator-worker orchestration behind the workflow API."""

from __future__ import annotations

import json
import math
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from typing import IO, Any, cast

from .project import Project, ProjectError

_MAX_OUTPUT = 32 * 1024 * 1024


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate worker JSON key")
        result[key] = value
    return result


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite worker JSON number")
    return number


def _reject(value):
    raise ValueError("Non-finite worker JSON number")


def execute(
    project: Project,
    operation: str,
    *,
    profile: str = "acceptance",
    target: str | None = None,
    allow_paid: bool = False,
) -> dict:
    """Execute reviewed evaluator code with only explicitly configured credentials.

    A worker owns one operation; target calls are separate processes. Completed
    observations survive a worker timeout. This does not sandbox hostile code or
    impose an atomic provider-side dollar cap.
    """
    if os.name != "posix":
        raise ProjectError("Evaluation execution requires Linux or macOS")
    if operation not in {"inspect", "audit", "run"} or profile not in project.contract.profiles:
        raise ProjectError("Unknown evaluator operation or profile")
    if (operation == "run" and target not in project.contract.targets) or (
        operation != "run" and target is not None
    ):
        raise ProjectError(
            "Run requires a configured target; inspect and audit do not take targets"
        )
    env_names = list(project.contract.evaluator_env)
    if target:
        env_names.extend(project.contract.targets[target].env)
    if any(name not in os.environ for name in env_names):
        raise ProjectError("A configured evaluator or target environment variable is absent")
    env = {
        name: os.environ[name]
        for name in ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", *env_names)
        if name in os.environ
    }
    env.pop("CONFIDENT_API_KEY", None)
    env.update(
        DEEPEVAL_DISABLE_DOTENV="1",
        DEEPEVAL_TELEMETRY_OPT_OUT="1",
        DEEPEVAL_UPDATE_WARNING_OPT_IN="0",
        CONFIDENT_TRACE_FLUSH="0",
        CONFIDENT_TRACE_SAMPLE_RATE="0",
        PYTHONDONTWRITEBYTECODE="1",
    )
    payload = json.dumps(
        {
            "root": str(project.root),
            "change": project.change,
            "operation": operation,
            "profile": profile,
            "target": target,
            "allow_paid": allow_paid,
        }
    ).encode()
    result: dict[str, Any] = {
        "cases": [],
        "controls": [],
        "metrics": {},
        "expected_ids": [],
        "expected_rows": [],
        "observations": [],
        "gaps": [],
        "control_gaps": [],
        "application_gaps": [],
        "review_gaps": [],
        "execution_errors": [],
        "observed_cost_usd": 0.0,
    }
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", "-m", "edd_kit.worker"],
            cwd=project.directory,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            shell=False,
            bufsize=0,
        )
    except OSError:
        result["execution_errors"].append("Evaluator worker could not be started")
        return result
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    pipes = (process.stdin, process.stdout, process.stderr)
    deadline = time.monotonic() + project.contract.profiles[profile].timeout_seconds
    pending = bytearray()
    output_size = 0
    sent = 0
    planned = False
    completed = False
    identities = {}
    observed = set()
    original_sigterm = None
    if threading.current_thread() is threading.main_thread():
        original_sigterm = signal.getsignal(signal.SIGTERM)

        def terminate(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, terminate)

    def consume(line):
        nonlocal planned, completed
        message = json.loads(
            line, object_pairs_hook=_unique, parse_float=_finite, parse_constant=_reject
        )
        if not isinstance(message, dict) or set(message) != {"type", "data"}:
            raise ValueError("Invalid worker envelope")
        kind, data = message["type"], message["data"]
        if not isinstance(data, dict) or completed:
            raise ValueError("Invalid worker stream")
        if kind == "plan" and not planned:
            if set(data) != {
                "cases",
                "controls",
                "metrics",
                "expected_ids",
                "expected_rows",
                "gaps",
                "control_gaps",
                "application_gaps",
                "review_gaps",
            }:
                raise ValueError("Invalid worker plan")
            if (
                not isinstance(data["metrics"], dict)
                or not all(
                    isinstance(data[key], list)
                    for key in (
                        "cases",
                        "controls",
                        "expected_ids",
                        "expected_rows",
                        "gaps",
                        "control_gaps",
                        "application_gaps",
                        "review_gaps",
                    )
                )
                or not all(
                    isinstance(gap, str)
                    for key in ("gaps", "control_gaps", "application_gaps", "review_gaps")
                    for gap in data[key]
                )
            ):
                raise ValueError("Invalid worker plan values")
            core = {"id", "case_id", "requirement_id", "trial", "repetition"}
            if operation == "audit":
                core |= {"control_id", "expected_pass"}
            for row in data["expected_rows"]:
                if (
                    not isinstance(row, dict)
                    or set(row) != core
                    or not all(
                        isinstance(row[key], str) for key in ("id", "case_id", "requirement_id")
                    )
                    or row["id"] in identities
                    or not all(
                        type(row[key]) is int and row[key] > 0 for key in ("trial", "repetition")
                    )
                    or (
                        operation == "audit"
                        and (
                            type(row["expected_pass"]) is not bool
                            or not isinstance(row["control_id"], str)
                        )
                    )
                ):
                    raise ValueError("Invalid expected observation identity")
                identities[row["id"]] = row
            if data["expected_ids"] != list(identities):
                raise ValueError("Observation IDs do not match the worker plan")
            result.update(data)
            planned = True
        elif kind == "observation" and planned:
            identity = identities.get(data.get("id"))
            if (
                identity is None
                or data["id"] in observed
                or any(data.get(key) != value for key, value in identity.items())
                or not all(type(data.get(key)) is int for key in ("trial", "repetition"))
                or data.get("passed") not in (True, False, None)
                or not isinstance(data.get("metadata"), dict)
                or not {"score", "passed", "reason", "error", "cost_usd", "actual_output"}.issubset(
                    data
                )
            ):
                raise ValueError("Observation does not match its planned identity")
            for key in ("reason", "error", "actual_output"):
                if data[key] is not None and not isinstance(data[key], str):
                    raise ValueError("Invalid observation text")
            for key in ("score", "cost_usd"):
                value = data[key]
                if value is not None and (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or value < 0
                    or (key == "score" and value > 1)
                ):
                    raise ValueError("Invalid observation number")
            if data["passed"] is not None and type(data["passed"]) is not bool:
                raise ValueError("Invalid observation outcome")
            observed.add(data["id"])
            result["observations"].append(data)
            if isinstance(data.get("cost_usd"), (int, float)):
                result["observed_cost_usd"] += data["cost_usd"]
        elif kind == "complete":
            if set(data) - {"gaps", "execution_errors", "observed_cost_usd"}:
                raise ValueError("Invalid completion")
            for key in ("gaps", "execution_errors"):
                if key in data and (
                    not isinstance(data[key], list)
                    or not all(isinstance(value, str) for value in data[key])
                ):
                    raise ValueError("Invalid completion diagnostics")
            if "observed_cost_usd" in data:
                cost = data.pop("observed_cost_usd")
                if (
                    type(cost) not in (int, float)
                    or not math.isfinite(cost)
                    or not math.isclose(cost, result["observed_cost_usd"], abs_tol=1e-12)
                ):
                    raise ValueError("Completion cost differs from measured observations")
            if not planned and not data.get("execution_errors"):
                raise ValueError("Successful completion without a plan")
            result.update(data)
            completed = True
        else:
            raise ValueError("Invalid worker message")

    try:
        with selectors.DefaultSelector() as selector:
            for stream, event in (
                (process.stdin, selectors.EVENT_WRITE),
                (process.stdout, selectors.EVENT_READ),
                (process.stderr, selectors.EVENT_READ),
            ):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                for key, _ in selector.select(min(remaining, 0.1)):
                    stream = cast(IO[bytes], key.fileobj)
                    if stream is process.stdin:
                        try:
                            sent += os.write(stream.fileno(), payload[sent : sent + 65_536])
                        except BrokenPipeError:
                            sent = len(payload)
                        if sent == len(payload):
                            selector.unregister(stream)
                            stream.close()
                        continue
                    chunk = os.read(stream.fileno(), min(65_536, _MAX_OUTPUT - output_size + 1))
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    output_size += len(chunk)
                    if output_size > _MAX_OUTPUT:
                        raise OverflowError
                    if stream is process.stdout:
                        pending.extend(chunk)
                        while b"\n" in pending:
                            line, _, rest = pending.partition(b"\n")
                            pending[:] = rest
                            consume(line)
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
        if pending or not completed or process.returncode != 0:
            result["execution_errors"].append("Evaluator worker ended without a valid completion")
    except (TimeoutError, subprocess.TimeoutExpired):
        result["execution_errors"].append("Evaluator operation exceeded its deadline")
    except OverflowError:
        result["execution_errors"].append("Evaluator output exceeded the 32 MiB limit")
    except (ValueError, TypeError, KeyError, UnicodeError, OSError):
        result["execution_errors"].append("Evaluator worker returned an invalid protocol stream")
    finally:
        # Let the worker's SIGTERM handler unwind invoke_target's child cleanup.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        for stream in pipes:
            stream.close()
        if original_sigterm is not None:
            signal.signal(signal.SIGTERM, original_sigterm)
    return result
