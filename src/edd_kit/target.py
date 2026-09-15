"""Run a cooperative application through a bounded JSON process protocol.

Process and environment separation prevent accidental evaluator/target mixing.
They do not sandbox hostile application code.
"""

from __future__ import annotations

import json
import math
import os
import re
import selectors
import signal
import subprocess
import time
from pathlib import Path
from typing import IO, cast


class TargetError(Exception):
    """A target invocation failed; ``code`` is stable and contains no secrets."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def _reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON constant")


def _response(output: bytearray) -> dict:
    try:
        response = json.loads(
            output,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
        if not isinstance(response, dict) or not isinstance(response.get("actual_output"), str):
            raise ValueError("Missing application output")
        if response.keys() - {
            "actual_output",
            "context",
            "retrieval_context",
            "tools_called",
            "metadata",
        }:
            raise ValueError("Unexpected response field")
        for field in ("context", "retrieval_context"):
            if field in response and (
                not isinstance(response[field], list)
                or not all(isinstance(value, str) for value in response[field])
            ):
                raise ValueError("Invalid context")
        if "tools_called" in response and (
            not isinstance(response["tools_called"], list)
            or not all(isinstance(value, dict) for value in response["tools_called"])
        ):
            raise ValueError("Invalid tools")
        if "metadata" in response and not isinstance(response["metadata"], dict):
            raise ValueError("Invalid metadata")
        return response
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise TargetError("protocol", "Target did not return a valid protocol response.") from None


def _request_bytes(request: dict) -> bytes:
    try:
        if not isinstance(request, dict) or not isinstance(request.get("input"), str):
            raise ValueError("Missing target input")
        if request.keys() - {"case_id", "input", "context", "metadata", "trial", "fixture"}:
            raise ValueError("Unexpected request field")
        if "context" in request and (
            not isinstance(request["context"], list)
            or not all(isinstance(value, str) for value in request["context"])
        ):
            raise ValueError("Invalid context")
        for field in ("metadata", "fixture"):
            if field in request and not isinstance(request[field], dict):
                raise ValueError("Invalid metadata or fixture")
        if "case_id" in request and not isinstance(request["case_id"], str):
            raise ValueError("Invalid case identity")
        if "trial" in request and (type(request["trial"]) is not int or request["trial"] < 0):
            raise ValueError("Invalid trial")
        return json.dumps(request, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        raise TargetError("configuration", "Target request is not valid protocol input.") from None


def invoke_target(
    command: list[str],
    request: dict,
    *,
    cwd: Path,
    env_names: list[str],
    timeout_seconds: float,
    max_output_bytes: int = 1_048_576,
) -> dict:
    """Invoke one target, retaining bounded stdout and discarding stderr.

    The combined stdout/stderr byte count is limited by ``max_output_bytes``.
    POSIX process groups ensure descendants are cleaned up on every exit path.
    ``KeyboardInterrupt`` and ``SystemExit`` propagate after cleanup.
    The owning worker must translate SIGTERM into an exception for cleanup.
    """
    if os.name != "posix":
        raise TargetError("configuration", "Target execution requires Linux or macOS.")
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
        or type(max_output_bytes) is not int
        or max_output_bytes <= 0
    ):
        raise TargetError("configuration", "Target execution limits must be finite and positive.")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(argument, str) and "\x00" not in argument for argument in command)
        or not command[0]
    ):
        raise TargetError("configuration", "Target command must be a nonempty argument list.")
    payload = _request_bytes(request)
    if not isinstance(env_names, list) or not all(
        isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
        for name in env_names
    ):
        raise TargetError("configuration", "Target environment names are invalid.")
    if any(name not in os.environ for name in env_names):
        raise TargetError("configuration", "A required target environment variable is absent.")
    child_env = {
        name: os.environ[name]
        for name in ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", *env_names)
        if name in os.environ
    }
    child_env.pop("CONFIDENT_API_KEY", None)
    child_env.update(
        DEEPEVAL_DISABLE_DOTENV="1",
        DEEPEVAL_TELEMETRY_OPT_OUT="1",
        DEEPEVAL_UPDATE_WARNING_OPT_IN="0",
        CONFIDENT_TRACE_FLUSH="0",
        CONFIDENT_TRACE_SAMPLE_RATE="0",
    )
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=child_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            bufsize=0,
        )
    except (OSError, ValueError):
        raise TargetError("spawn", "Target process could not be started.") from None
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    pipes = (process.stdin, process.stdout, process.stderr)
    deadline = time.monotonic() + timeout_seconds
    output = bytearray()
    output_size = 0
    sent = 0
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
                    raise TargetError("timeout", "Target exceeded its execution deadline.")
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
                    else:
                        chunk = os.read(
                            stream.fileno(), min(65_536, max_output_bytes - output_size + 1)
                        )
                        if not chunk:
                            selector.unregister(stream)
                            stream.close()
                        else:
                            output_size += len(chunk)
                            if output_size > max_output_bytes:
                                raise TargetError(
                                    "output_limit", "Target output exceeded the byte limit."
                                )
                            if stream is process.stdout:
                                output.extend(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TargetError("timeout", "Target exceeded its execution deadline.")
        try:
            exit_code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise TargetError("timeout", "Target exceeded its execution deadline.") from None
        if exit_code != 0:
            raise TargetError("exit", "Target exited unsuccessfully.")
        return _response(output)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        for stream in pipes:
            stream.close()
