"""Project configuration, file ownership, and reproducible local evidence identities."""

import errno
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any

from . import __version__
from .models import Contract


class ProjectError(ValueError):
    """An actionable invalid project configuration or evidence error."""


def project_root(root: Path) -> Path:
    """Resolve a project location without following an explicitly linked root."""
    root = Path(root)
    if root.is_symlink():
        raise ProjectError("Project root must not be a symlink")
    try:
        root = root.resolve()
    except (OSError, RuntimeError) as exc:
        raise ProjectError("Cannot resolve project root") from exc
    if root.exists() and not root.is_dir():
        raise ProjectError("Project root must be a directory")
    return root


def changes_directory(root: Path) -> Path:
    """Load and validate the v1 configuration before using its managed directory."""
    root = project_root(root)
    try:
        config = tomllib.loads(safe_path(root, "edd.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ProjectError("Invalid edd.toml; initialize with edd init") from exc
    if (
        set(config) != {"schema_version", "changes_dir"}
        or type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or not isinstance(config["changes_dir"], str)
        or not config["changes_dir"].strip()
    ):
        raise ProjectError("Unsupported edd.toml; expected schema_version = 1 and changes_dir text")
    directory = safe_path(root, config["changes_dir"], must_exist=False)
    if directory.exists() and not directory.is_dir():
        raise ProjectError("Configured changes_dir must be a directory")
    return directory


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path: Path) -> Any:
    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ProjectError("JSON number is outside the finite supported range")
        return number

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProjectError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ProjectError(f"JSON file exceeds 32 MiB: {path.name}")
        return json.loads(
            path.read_text(),
            object_pairs_hook=unique,
            parse_float=finite,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ProjectError(f"Invalid JSON number: {value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProjectError(f"Cannot read valid JSON from {path.name}") from exc


def safe_path(root: Path, relative: str, *, must_exist: bool = True) -> Path:
    if not isinstance(relative, str) or not relative.strip() or "\x00" in relative:
        raise ProjectError("Expected a nonempty project-relative path")
    value = Path(relative)
    if (
        value.is_absolute()
        or not value.parts
        or any(part in {"..", ".git"} for part in value.parts)
    ):
        raise ProjectError(f"Expected a project-relative path: {relative}")
    path = root
    for part in value.parts:
        path = path / part
        if path.is_symlink():
            raise ProjectError(f"Refusing symlink path: {relative}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ProjectError(f"Path leaves project: {relative}")
    if must_exist and not path.exists():
        raise ProjectError(f"Missing file or directory: {relative}")
    return path


def file_hashes(root: Path, path: Path) -> dict[str, str]:
    result = {}
    paths = [path] if path.is_file() else sorted(path.rglob("*"))
    for item in paths:
        if "__pycache__" in item.parts or item.suffix in {".pyc", ".pyo"}:
            continue
        if item.is_symlink():
            raise ProjectError(f"Refusing symlink in evidence bundle: {item.relative_to(root)}")
        if item.is_file():
            if item.stat().st_size > 64 * 1024 * 1024:
                raise ProjectError(f"Artifact exceeds 64 MiB: {item.relative_to(root)}")
            result[item.relative_to(root).as_posix()] = hashlib.sha256(
                item.read_bytes()
            ).hexdigest()
    return result


def runtime_identity() -> dict:
    packages = sorted(
        (dist.metadata["Name"].lower(), dist.version)
        for dist in importlib.metadata.distributions()
        if dist.metadata["Name"]
    )
    implementation = file_hashes(Path(__file__).parent, Path(__file__).parent)
    return {
        "edd": __version__,
        "python": platform.python_version(),
        "platform": sys.platform,
        "packages": packages,
        "implementation": implementation,
    }


class Project:
    def __init__(self, root: Path, change: str):
        self.root = project_root(root)
        if not isinstance(change, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", change):
            raise ProjectError("Change must be a lowercase name containing letters, digits, - or _")
        self.change = change
        changes = changes_directory(self.root)
        self.directory = safe_path(self.root, str(changes.relative_to(self.root) / change))
        self.contract_path = safe_path(
            self.root, str(self.directory.relative_to(self.root) / "contract.json")
        )
        try:
            self.contract = Contract.model_validate(read_json(self.contract_path))
        except ValueError as exc:
            raise ProjectError(f"Invalid contract: {exc}") from exc
        if self.contract.change != change:
            raise ProjectError("Contract change does not match its directory")
        suite_path, self.entrypoint = self.contract.suite.split(":", 1)
        self.suite_path = safe_path(self.directory, suite_path)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.entrypoint):
            raise ProjectError("Invalid suite entrypoint function name")
        self.state = safe_path(self.root, f".edd/{change}", must_exist=False)

    def criteria_identity(self) -> dict:
        contract = self.contract.model_dump(exclude={"targets"})
        files = file_hashes(self.root, self.directory)
        files.pop(self.contract_path.relative_to(self.root).as_posix())
        files.pop((self.directory / "review.json").relative_to(self.root).as_posix(), None)
        files.pop((self.directory / "REVIEW.md").relative_to(self.root).as_posix(), None)
        for artifact in self.contract.artifacts:
            files.update(file_hashes(self.root, safe_path(self.root, artifact)))
        # The normalized acceptance contract is independent of target configuration.
        files.pop(self.contract_path.relative_to(self.root).as_posix(), None)
        files.pop((self.directory / "review.json").relative_to(self.root).as_posix(), None)
        files.pop((self.directory / "REVIEW.md").relative_to(self.root).as_posix(), None)
        return {"contract": contract, "files": files}

    def criteria_digest(self) -> str:
        return digest(self.criteria_identity())

    def bundle_identity(self) -> dict:
        return {
            "criteria": self.criteria_identity(),
            "runtime": runtime_identity(),
            "evaluator_env": self._env_identity(self.contract.evaluator_env),
        }

    def bundle_digest(self) -> str:
        return digest(self.bundle_identity())

    def _env_identity(self, names: list[str]) -> dict:
        return {name: digest(os.environ[name]) if name in os.environ else None for name in names}

    def target_identity(self, name: str) -> dict:
        if name not in self.contract.targets:
            raise ProjectError(f"Unknown target: {name}")
        target = self.contract.targets[name]
        files = {}
        for artifact in target.files:
            path = safe_path(self.root, artifact)
            if path.is_relative_to(self.directory) or self.directory.is_relative_to(path):
                raise ProjectError("Target code must be separate from the evaluation directory")
            files.update(file_hashes(self.root, path))
        if not files:
            raise ProjectError("Target files must include at least one file")
        if files.keys() & self.criteria_identity()["files"].keys():
            raise ProjectError("Target code must be separate from evaluation artifacts")
        # Common adapter scripts/config arguments must not escape the declared identity. Other
        # imports, shell-embedded paths and remote dependencies still require explicit declaration.
        for argument in target.command[1:]:
            argument_path = Path(argument)
            path = argument_path if argument_path.is_absolute() else self.root / argument_path
            if not path.is_relative_to(self.root):
                continue
            try:
                local_file = path.is_file()
            except OSError as exc:
                if exc.errno == errno.ENAMETOOLONG:
                    continue  # Inline code/data, not a possible local filename.
                raise ProjectError("Cannot inspect a target command file argument") from exc
            if local_file:
                path = safe_path(self.root, str(path.relative_to(self.root)))
                if path.relative_to(self.root).as_posix() not in files:
                    raise ProjectError(
                        "Local command file arguments must be listed in target.files"
                    )
        command = target.command[0]
        if not Path(command).is_absolute() and os.path.dirname(command):
            command = str(self.root / command)
        search_path = os.pathsep.join(
            str(Path(entry) if Path(entry).is_absolute() else self.root / entry)
            for entry in os.environ.get("PATH", os.defpath).split(os.pathsep)
        )
        executable = shutil.which(command, path=search_path)
        if executable is None:
            raise ProjectError(f"Target executable not found: {target.command[0]}")
        executable_path = Path(executable).resolve()
        try:
            with executable_path.open("rb") as stream:
                executable_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        except OSError as exc:
            raise ProjectError("Cannot fingerprint target executable") from exc
        return {
            "config": target.model_dump(),
            "files": files,
            "executable": str(executable_path),
            "executable_sha256": executable_sha256,
            "env": self._env_identity(target.env),
        }

    def target_digest(self, name: str) -> str:
        return digest(self.target_identity(name))
