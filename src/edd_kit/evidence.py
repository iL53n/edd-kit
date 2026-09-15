"""Atomic local records. Checksums detect corruption; they are not signatures."""

import contextlib
import datetime as dt
import os
import tempfile
import uuid
from pathlib import Path

from .project import ProjectError, canonical, digest, read_json, safe_path


def timestamp() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="microseconds")


def new_id() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]


def _check_record_path(path: Path) -> None:
    if ".." in path.parts:
        raise ProjectError("Refusing parent traversal in evidence path")
    if any(ancestor.is_symlink() for ancestor in (path, *path.absolute().parents)):
        raise ProjectError("Refusing symlink evidence path")


def write_record(path: Path, payload: dict) -> None:
    _check_record_path(path)
    if not isinstance(payload, dict):
        raise ProjectError("Evidence payload must be an object")
    try:
        data = canonical({"schema_version": 1, "payload": payload, "sha256": digest(payload)})
    except (TypeError, ValueError) as exc:
        raise ProjectError("Evidence payload must contain valid finite JSON values") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    _check_record_path(path)
    fd, temporary = tempfile.mkstemp(prefix=".edd-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.write(b"\n")
            output.flush()
            os.fsync(output.fileno())
        _check_record_path(path)
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def read_record(path: Path) -> dict:
    _check_record_path(path)
    data = read_json(path)
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "payload", "sha256"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["payload"], dict)
        or data["sha256"] != digest(data["payload"])
    ):
        raise ProjectError(f"Invalid or corrupted evidence: {path.name}")
    return data["payload"]


@contextlib.contextmanager
def project_lock(root: Path, state: Path):
    if os.name != "posix":
        raise ProjectError("EDD execution requires Linux or macOS")
    import fcntl

    safe_path(root, str(state.relative_to(root)), must_exist=False)
    state.mkdir(parents=True, exist_ok=True)
    lock = state / ".lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ProjectError("Another EDD operation is running for this change") from exc
        yield
    finally:
        os.close(fd)


def redact(value, secrets: list[str]):
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    return value
