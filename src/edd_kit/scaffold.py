"""Install project scaffolding without replacing user-authored content."""

import json
import re
import tomllib
from hashlib import sha256
from importlib.resources import files as resource_files
from pathlib import Path
from typing import Any


def _project_root(root: Path) -> Path:
    root = Path(root)
    if root.is_symlink():
        raise ValueError("project root must not be a symlink")
    root = root.resolve()
    if root.exists() and not root.is_dir():
        raise ValueError("project root must be a directory")
    return root


def _destination(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in {"..", ".git"} for part in path.parts):
        raise ValueError(f"path must stay inside the project: {relative}")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"managed path must not contain a symlink: {relative}")
        if current != root / path and current.exists() and not current.is_dir():
            raise ValueError(f"managed parent must be a directory: {relative}")
    if current.exists() and not current.is_file():
        raise ValueError(f"managed file path is not a file: {relative}")
    return current


def init_project(root: Path, agent: str = "codex") -> dict:
    """Initialize local EDD configuration, preserving existing project files."""
    if agent not in {"codex", "claude", "none"}:
        raise ValueError("agent must be codex, claude, or none")
    root = _project_root(root)
    result: dict[str, Any] = {
        "root": str(root),
        "agent": agent,
        "created": [],
        "updated": [],
        "preserved": [],
        "conflicts": [],
    }
    files = {
        "edd.toml": 'schema_version = 1\nchanges_dir = "evals"\n',
        ".edd/.gitignore": "*\n!.gitignore\n",
    }
    for relative in files:
        _destination(root, relative)
    sync_skills(root, agent=agent, preview=True)
    root.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        destination = _destination(root, relative)
        if destination.exists():
            result["preserved"].append(relative)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(content)
        result["created"].append(relative)
    skills = sync_skills(root, agent=agent, preview=False)
    for key in ("created", "updated", "preserved", "conflicts"):
        result[key].extend(skills[key])
    return result


def _packaged_skills(agent: str) -> dict[str, bytes]:
    if agent not in {"codex", "claude", "none"}:
        raise ValueError("agent must be codex, claude, or none")
    if agent == "none":
        return {}
    destination = ".agents/skills" if agent == "codex" else ".claude/skills"
    packaged = resource_files("edd_kit").joinpath("assets", "skills")
    contents = {}

    def collect(directory, prefix):
        for entry in directory.iterdir():
            if entry.name == "__pycache__" or entry.name.startswith("."):
                continue
            relative = f"{prefix}/{entry.name}"
            if entry.is_dir():
                collect(entry, relative)
            elif entry.is_file() and not entry.name.endswith(".pyc"):
                contents[relative] = entry.read_bytes()

    collect(packaged, destination)
    if not contents:
        raise ValueError("EDD skill resources are missing from this installation")
    return contents


def sync_skills(root: Path, agent: str = "codex", *, preview: bool = True) -> dict:
    """Preview or synchronize packaged skills while preserving locally edited files."""
    root = _project_root(root)
    contents = _packaged_skills(agent)
    result: dict[str, Any] = {
        "root": str(root),
        "agent": agent,
        "preview": preview,
        "created": [],
        "updated": [],
        "preserved": [],
        "conflicts": [],
    }
    if not contents:
        return result
    manifest_path = _destination(root, ".edd/skills.json")
    manifest: dict[str, Any] = {"schema_version": 1, "files": {}}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), dict):
                raise ValueError("unsupported skill manifest")
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"cannot read .edd/skills.json: {exc}") from exc
    updates = {}
    baseline_hashes = {}
    for relative, content in sorted(contents.items()):
        destination = _destination(root, relative)
        wanted = sha256(content).hexdigest()
        if not destination.exists():
            result["created"].append(relative)
            updates[relative] = content
            manifest["files"][relative] = wanted
            continue
        current = sha256(destination.read_bytes()).hexdigest()
        if current == wanted:
            result["preserved"].append(relative)
            manifest["files"][relative] = wanted
        elif manifest["files"].get(relative) == current:
            result["updated"].append(relative)
            updates[relative] = content
            baseline_hashes[relative] = current
            manifest["files"][relative] = wanted
        else:
            result["conflicts"].append(relative)
    if preview:
        return result
    for relative, content in updates.items():
        destination = _destination(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if relative in baseline_hashes:
            if sha256(destination.read_bytes()).hexdigest() != baseline_hashes[relative]:
                raise ValueError(f"skill changed during synchronization: {relative}")
            destination.write_bytes(content)
        else:
            with destination.open("xb") as stream:
                stream.write(content)
    manifest_content = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if not manifest_path.exists() or manifest_path.read_text(encoding="utf-8") != manifest_content:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(manifest_content, encoding="utf-8")
    return result


def prepare_change(root: Path, change: str, brief: str, template: str = "starter") -> dict:
    """Create a reviewable eval draft; do not infer feature semantics from prose."""
    root = _project_root(root)
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", change):
        raise ValueError(
            "change must start with a lowercase letter and contain at most 64 lowercase "
            "letters, digits, hyphens, or underscores"
        )
    if template not in {"starter", "cancellation"}:
        raise ValueError("unknown template; choose starter or cancellation")
    if not brief.strip():
        raise ValueError("brief must describe the intended behavior")
    if not _destination(root, "edd.toml").is_file():
        raise ValueError("initialize the project with edd init before preparing a change")
    try:
        config = tomllib.loads((root / "edd.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("cannot read valid edd.toml") from exc
    if set(config) != {"schema_version", "changes_dir"} or config["schema_version"] != 1:
        raise ValueError("unsupported edd.toml; expected schema_version = 1 and changes_dir")
    changes_dir = config["changes_dir"]
    if not isinstance(changes_dir, str) or not changes_dir.strip():
        raise ValueError("changes_dir must be a nonempty project-relative directory")
    path = Path(changes_dir)
    if path.is_absolute() or not path.parts or any(part in {"..", ".git"} for part in path.parts):
        raise ValueError("changes_dir must stay inside the project and outside .git")
    eval_directory = f"{path.as_posix()}/{change}"
    resources = resource_files("edd_kit").joinpath("assets", "templates", template)
    contents = {}
    contents[f"{eval_directory}/eval-requirements.lock"] = (
        resource_files("edd_kit").joinpath("assets", "requirements-eval.lock").read_text()
    )
    for resource in resources.iterdir():
        if resource.is_file():
            filename = resource.name
            relative_destination = (
                f"targets/{change}/{filename.removeprefix('target-')}"
                if filename.startswith("target-")
                else f"{eval_directory}/{filename}"
            )
            contents[relative_destination] = resource.read_text(encoding="utf-8").replace(
                "{{change}}", change
            )
    contents[f"{eval_directory}/brief.md"] = (
        f"# {change}\n\n{brief.rstrip()}\n\n"
        "## Preparation status\n\n"
        "This starter is an unreviewed example, not acceptance evidence for the described feature. "
        "Adapt the cases, graders, target adapter, and control labels to the intended behavior "
        "before reviewing the contract. The command creates scaffolding; the coding-agent skill "
        "authors the domain evaluation.\n"
    )
    if template == "cancellation":
        contents[f"{eval_directory}/brief.md"] = (
            f"# {change}\n\n{brief.rstrip()}\n\n"
            "## Synthetic reference workflow\n\n"
            "This offline toy application changes an in-memory orders fixture. It is not an LLM "
            "assistant or evidence about production behavior. Only the signed-in owner may cancel "
            "an active order. Other customers' orders and already-cancelled orders remain "
            "unchanged.\n\n"
            "The candidate implements that small behavior. The stub demonstrates missing "
            "capability; noop claims success without changing state; wrong-owner omits "
            "authorization. The native "
            "DeepEval graders compare observed state with worked examples and check ownership.\n\n"
            "Controls are labeled by the synthetic fixture authors; a person must still review the "
            "contract. A production adapter must collect authoritative state independently of the "
            "application's claims. Replace these synthetic cases with domain-reviewed evidence.\n"
        )
    for directory in (eval_directory, f"targets/{change}"):
        _destination(root, f"{directory}/.path-check")
        if (root / directory).exists():
            raise ValueError(f"change directory already exists: {directory}")
    for relative in contents:
        _destination(root, relative)
    created = []
    for relative, content in contents.items():
        destination = _destination(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(content)
        created.append(relative)
    return {
        "root": str(root),
        "change": change,
        "created": created,
        "preserved": [],
        "conflicts": [],
    }
