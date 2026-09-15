"""Specialist packets, semantic revisions, and repository-visible review history."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .evidence import new_id, read_record, timestamp
from .project import Project, ProjectError, read_json


def packet_content(project: Project, inspection: dict) -> dict:
    requirements = {
        requirement.id: {
            "description": requirement.description,
            "critical": requirement.critical,
            "minimum_pass_rate": requirement.pass_rate,
            "minimum_cases": requirement.min_cases,
        }
        for requirement in project.contract.requirements
    }
    controls = [
        {
            "id": row["control_id"],
            "requirement_id": row["requirement_id"],
            "case_id": row.get("case_id"),
            "expected": "accept" if row["expected_pass"] else "reject",
            "source": row["source"],
            "partition": row["partition"],
            "rationale": row.get("rationale", ""),
            "contributed_by": row.get("contributed_by", ""),
            "independent": row.get("independent", False),
            "evidence": row.get("evidence", {}),
        }
        for row in inspection.get("controls", [])
    ]
    return {
        "schema_version": 2,
        "kind": "review-packet",
        "change": project.change,
        "title": project.contract.title,
        "criteria_digest": project.criteria_digest(),
        "requirements": requirements,
        "cases": inspection.get("cases", []),
        "controls": controls,
        "metrics": inspection.get("metrics", {}),
        "targets": inspection.get("targets", {}),
        "acceptance_profile": project.contract.profiles["acceptance"].model_dump(),
        "execution_errors": inspection.get("execution_errors", []),
        "gaps": inspection.get("gaps", []),
        "review_gaps": inspection.get("review_gaps", []),
    }


def criteria_snapshot(project: Project, packet: dict) -> dict:
    return {
        "requirements": packet["requirements"],
        "cases": packet["cases"],
        "controls": packet["controls"],
        "metrics": packet["metrics"],
        "acceptance_profile": packet["acceptance_profile"],
        "criteria_files": project.criteria_identity()["files"],
    }


def review_path(project: Project) -> Path:
    return project.directory / "review.json"


def load_review(project: Project) -> dict | None:
    path = review_path(project)
    if not path.is_file():
        return None
    raw = read_json(path)
    if isinstance(raw, dict) and set(raw) == {"schema_version", "payload", "sha256"}:
        return read_record(path)
    if not isinstance(raw, dict):
        raise ProjectError("Invalid review metadata")
    return raw


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_log(project: Project, log: dict) -> None:
    if (
        log.get("schema_version") != 2
        or log.get("kind") != "review-log"
        or log.get("change") != project.change
        or not isinstance(log.get("versions"), list)
    ):
        raise ProjectError("Invalid review metadata")
    digests: set[str] = set()
    event_ids: set[str] = set()
    for version in log["versions"]:
        if (
            not isinstance(version, dict)
            or not isinstance(version.get("criteria_digest"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", version["criteria_digest"])
            or version["criteria_digest"] in digests
            or not isinstance(version.get("snapshot"), dict)
            or not isinstance(version.get("events"), list)
            or (
                "review_packet_digest" in version
                and (
                    not isinstance(version["review_packet_digest"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", version["review_packet_digest"])
                )
            )
        ):
            raise ProjectError("Invalid review metadata")
        digests.add(version["criteria_digest"])
        for event in version["events"]:
            if (
                not isinstance(event, dict)
                or event.get("area") not in {"domain", "technical"}
                or event.get("decision") not in {"approve", "request_changes", "needs_discussion"}
                or any(
                    not _valid_text(event.get(key))
                    for key in ("id", "created_at", "reviewer", "rationale")
                )
                or event["id"] in event_ids
                or (event.get("subject") is not None and not _valid_text(event["subject"]))
            ):
                raise ProjectError("Invalid review metadata")
            try:
                if datetime.fromisoformat(event["created_at"]).utcoffset() is None:
                    raise ValueError
            except ValueError as exc:
                raise ProjectError("Invalid review metadata timestamp") from exc
            event_ids.add(event["id"])


def _write_log(path: Path, payload: dict) -> None:
    if path.is_symlink():
        raise ProjectError("Refusing symlink review path")
    data = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".edd-review-log-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if path.is_symlink():
            raise ProjectError("Refusing symlink review path")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def record_decision(
    project: Project,
    *,
    packet: dict,
    area: str,
    decision: str,
    reviewer: str,
    rationale: str,
    subject: str | None,
) -> dict:
    existing = load_review(project)
    log: dict[str, Any]
    if existing is None or existing.get("schema_version") == 1:
        log = {
            "schema_version": 2,
            "kind": "review-log",
            "change": project.change,
            "versions": [],
        }
    else:
        _validate_log(project, existing)
        log = existing
    criteria_digest = packet["criteria_digest"]
    version = next(
        (item for item in log["versions"] if item["criteria_digest"] == criteria_digest), None
    )
    if version is None:
        version = {
            "criteria_digest": criteria_digest,
            "review_packet_digest": hashlib.sha256(packet["markdown"].encode()).hexdigest(),
            "snapshot": criteria_snapshot(project, packet),
            "events": [],
        }
        log["versions"].append(version)
    event = {
        "id": new_id(),
        "created_at": timestamp(),
        "area": area,
        "decision": decision,
        "reviewer": reviewer.strip(),
        "rationale": rationale.strip(),
        "subject": subject,
    }
    version["events"].append(event)
    _validate_log(project, log)
    _write_log(review_path(project), log)
    return event


def review_state(project: Project, log: dict | None = None) -> dict:
    log = load_review(project) if log is None else log
    if log is None:
        return {
            "status": "missing",
            "domain": {"status": "missing"},
            "technical": {"status": "missing"},
            "blockers": [],
        }
    if log.get("schema_version") == 1:
        if (
            log.get("kind") != "review"
            or log.get("change") != project.change
            or any(
                not _valid_text(log.get(key))
                for key in ("id", "created_at", "reviewer", "note", "criteria_digest")
            )
            or not re.fullmatch(r"[a-f0-9]{64}", log["criteria_digest"])
        ):
            raise ProjectError("Invalid review metadata")
        return {
            **log,
            "status": "legacy",
            "domain": {"status": "legacy"},
            "technical": {"status": "legacy"},
            "blockers": [],
        }
    _validate_log(project, log)
    current = next(
        (
            version
            for version in log["versions"]
            if version["criteria_digest"] == project.criteria_digest()
        ),
        None,
    )
    if current is None:
        last_digest = log["versions"][-1]["criteria_digest"] if log["versions"] else None
        return {
            "status": "stale",
            "criteria_digest": last_digest,
            "domain": {"status": "stale"},
            "technical": {"status": "stale"},
            "blockers": [],
        }
    areas: dict[str, dict] = {}
    blockers = []
    for area in ("domain", "technical"):
        events = [event for event in current["events"] if event["area"] == area]
        approval_index = max(
            (
                index
                for index, event in enumerate(events)
                if event["decision"] == "approve" and event["subject"] is None
            ),
            default=-1,
        )
        unresolved = [
            event
            for index, event in enumerate(events)
            if index > approval_index and event["decision"] != "approve"
        ]
        if unresolved:
            state = unresolved[-1]["decision"]
            blockers.extend(unresolved)
        elif approval_index >= 0:
            state = "approved"
        else:
            state = "missing"
        areas[area] = {"status": state, "latest": events[-1] if events else None}
    return {
        "status": (
            "current" if all(areas[area]["status"] == "approved" for area in areas) else "pending"
        ),
        "criteria_digest": current["criteria_digest"],
        "domain": areas["domain"],
        "technical": areas["technical"],
        "blockers": blockers,
    }


def stored_packet_status(project: Project, log: dict | None = None) -> str:
    path = packet_path(project)
    if not path.is_file():
        return "missing"
    try:
        payload = path.read_bytes()
    except OSError:
        return "stale"
    log = load_review(project) if log is None else log
    if log and log.get("schema_version") == 2:
        _validate_log(project, log)
        version = next(
            (
                item
                for item in log["versions"]
                if item["criteria_digest"] == project.criteria_digest()
            ),
            None,
        )
        if version is not None and isinstance(version.get("review_packet_digest"), str):
            return (
                "current"
                if hashlib.sha256(payload).hexdigest() == version["review_packet_digest"]
                else "stale"
            )
    marker = f"Criteria version: `{project.criteria_digest()}`".encode()
    return "current" if marker in payload else "stale"


def _item_map(items: object, key: str) -> dict:
    if not isinstance(items, list):
        return {}
    return {item[key]: item for item in items if isinstance(item, dict) and key in item}


def semantic_diff(before: dict | None, after: dict) -> list[dict]:
    if before is None:
        return []
    result = []
    collections = (
        ("requirement", "requirements", None),
        ("case", "cases", "case_id"),
        ("control", "controls", "id"),
        ("grader", "metrics", None),
    )
    for kind, field, list_key in collections:
        old = before.get(field, {})
        new = after.get(field, {})
        if list_key:
            old, new = _item_map(old, list_key), _item_map(new, list_key)
        if not isinstance(old, dict) or not isinstance(new, dict):
            continue
        for item_id in sorted(set(old) | set(new)):
            old_item, new_item = old.get(item_id), new.get(item_id)
            if old_item is None or new_item is None:
                result.append(
                    {
                        "subject": f"{kind}:{item_id}",
                        "field": "item",
                        "before": old_item,
                        "after": new_item,
                    }
                )
                continue
            if not isinstance(old_item, dict) or not isinstance(new_item, dict):
                if old_item != new_item:
                    result.append(
                        {
                            "subject": f"{kind}:{item_id}",
                            "field": "value",
                            "before": old_item,
                            "after": new_item,
                        }
                    )
                continue
            for name in sorted(set(old_item) | set(new_item)):
                if old_item.get(name) != new_item.get(name):
                    result.append(
                        {
                            "subject": f"{kind}:{item_id}",
                            "field": name,
                            "before": old_item.get(name),
                            "after": new_item.get(name),
                        }
                    )
    for name in ("acceptance_profile", "criteria_files"):
        old, new = before.get(name, {}), after.get(name, {})
        for field in sorted(set(old) | set(new)):
            if old.get(field) != new.get(field):
                result.append(
                    {
                        "subject": name.replace("_", ":"),
                        "field": field,
                        "before": old.get(field),
                        "after": new.get(field),
                    }
                )
    return result


def revision_diff(project: Project, packet: dict) -> list[dict]:
    log = load_review(project)
    if not log or log.get("schema_version") != 2:
        return []
    _validate_log(project, log)
    previous = next(
        (
            version
            for version in reversed(log["versions"])
            if version["criteria_digest"] != packet["criteria_digest"]
        ),
        None,
    )
    return semantic_diff(
        previous["snapshot"] if previous else None,
        criteria_snapshot(project, packet),
    )


def _block(value: object) -> list[str]:
    if value is None:
        return ["_None declared._"]
    text = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True)
    longest = max((len(value) for value in re.findall(r"~+", text)), default=0)
    fence = "~" * max(4, longest + 1)
    return [f"{fence}text", text, fence]


def render_markdown(packet: dict) -> str:
    lines = [
        f"# EDD review: {packet['title']}",
        "",
        f"Change: `{packet['change']}`  ",
        f"Criteria version: `{packet['criteria_digest']}`",
        "",
        "Review this file in the pull request. Record decisions with `edd review`; do not edit",
        "this generated packet or treat it as the canonical criteria.",
        "",
        "## Revision since previous review",
        "",
    ]
    differences = packet.get("revision_diff", [])
    if differences:
        for row in differences:
            lines.extend(
                [
                    f"### `{row['subject']}` / `{row['field']}`",
                    "",
                    "Before:",
                    "",
                    *_block(row["before"]),
                    "",
                    "After:",
                    "",
                    *_block(row["after"]),
                    "",
                ]
            )
    else:
        lines.append("No earlier reviewed criteria version is available for comparison.")
    lines.extend(
        [
            "",
            "## Domain expectations",
            "",
            "Approve this section only when the scenarios represent the intended business "
            "behavior.",
        ]
    )
    for requirement_id, requirement in packet["requirements"].items():
        critical = "critical" if requirement["critical"] else "non-critical"
        lines.extend(
            [
                "",
                f"### Requirement `{requirement_id}` ({critical})",
                "",
                requirement["description"],
                "",
                f"Minimum: {requirement['minimum_cases']} cases at "
                f"{requirement['minimum_pass_rate']:.0%} pass rate.",
            ]
        )
    lines.extend(["", "### Scenarios"])
    for case in packet["cases"]:
        rules = ", ".join(f"`{value}`" for value in case["requirements"])
        lines.extend(
            [
                "",
                f"#### Scenario `{case['case_id']}`",
                "",
                case.get("description") or "_Description missing._",
                "",
                f"Relevant rules: {rules}  ",
                f"Expected behavior: {case.get('expected_behavior') or '_Missing._'}",
                "",
                "Input:",
                "",
                *_block(case.get("input")),
                "",
                "Reference output:",
                "",
                *_block(case.get("reference_output")),
                "",
                "Acceptable alternatives:",
            ]
        )
        alternatives = case.get("acceptable_alternatives", [])
        lines.extend([f"- {value}" for value in alternatives] or ["- None declared."])
        lines.extend(["", "Unacceptable behavior:"])
        unacceptable = case.get("unacceptable_behaviors", [])
        lines.extend([f"- {value}" for value in unacceptable] or ["- None declared."])
    lines.extend(
        [
            "",
            "## Technical validation",
            "",
            "Approve this section only when the grader evidence measures the domain expectations.",
            "",
            "### Graders",
        ]
    )
    for requirement_id, metric in packet["metrics"].items():
        lines.extend(
            [
                "",
                f"- `{requirement_id}`: `{metric.get('metric_class')}`; threshold "
                f"`{metric.get('threshold')}`; provider-backed `{metric.get('requires_paid')}`",
            ]
        )
    lines.extend(["", "### Known controls"])
    for control in packet["controls"]:
        evidence = control["evidence"]
        lines.extend(
            [
                "",
                f"#### Control `{control['id']}` — {control['expected']}",
                "",
                f"Requirement: `{control['requirement_id']}`  ",
                f"Contributor: {control['contributed_by'] or '_Missing._'}  ",
                f"Independent of grader author: `{control['independent']}`  ",
                f"Source: {control['source']}  ",
                f"Rationale: {control['rationale'] or '_Missing._'}",
                "",
                "Input:",
                "",
                *_block(evidence.get("input")),
                "",
                "Reference output:",
                "",
                *_block(evidence.get("expected_output")),
                "",
                "Observed output supplied to the grader:",
                "",
                *_block(evidence.get("actual_output")),
            ]
        )
    lines.extend(
        [
            "",
            "> Passing these controls does not prove that a grader is universally reliable; it",
            "> shows only that the grader handled the declared examples under this configuration.",
            "",
            "## Review checklist",
            "",
            "- [ ] Domain expectations represent the business rule.",
            "- [ ] Technical validation measures those expectations.",
            "- [ ] Unresolved questions are recorded as blockers.",
            "",
        ]
    )
    return "\n".join(lines)


def packet_status(project: Project, expected: str) -> str:
    path = project.directory / "REVIEW.md"
    if not path.is_file():
        return "missing"
    try:
        return "current" if path.read_bytes() == expected.encode("utf-8") else "stale"
    except OSError:
        return "stale"


def packet_path(project: Project) -> Path:
    return project.directory / "REVIEW.md"
