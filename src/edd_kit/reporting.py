"""Consolidated human and machine-readable acceptance evidence."""

from __future__ import annotations

import json
import os
import tempfile

from .evidence import timestamp
from .project import Project, ProjectError, safe_path


def _evidence_summary(run: dict | None, status: dict, fresh: set[str]) -> dict:
    if run is None:
        return {"status": "missing", "origin": "saved"}
    return {
        **status,
        "id": run["id"],
        "origin": "fresh" if run["id"] in fresh else "saved",
    }


def build_report(
    project: Project,
    *,
    packet: dict,
    verification: dict,
    audit: dict | None,
    candidate: dict | None,
    fresh_run_ids: set[str],
    application_revision: str | None,
) -> dict:
    candidate_observations: dict[str, list[dict]] = {}
    for observation in (candidate or {}).get("observations", []):
        candidate_observations.setdefault(observation["case_id"], []).append(
            {
                key: observation.get(key)
                for key in (
                    "requirement_id",
                    "trial",
                    "repetition",
                    "passed",
                    "score",
                    "reason",
                    "error",
                    "actual_output",
                )
            }
        )
    audit_observations = {
        observation["control_id"]: observation
        for observation in (audit or {}).get("observations", [])
    }
    cases = [
        {
            "id": case["case_id"],
            "description": case.get("description"),
            "expected_behavior": case.get("expected_behavior"),
            "reference_output": case.get("reference_output"),
            "observations": candidate_observations.get(case["case_id"], []),
        }
        for case in packet["cases"]
    ]
    controls = []
    for control in packet["controls"]:
        observation = audit_observations.get(control["id"])
        controls.append(
            {
                "id": control["id"],
                "requirement_id": control["requirement_id"],
                "expected": control["expected"],
                "rationale": control["rationale"],
                "contributed_by": control["contributed_by"],
                "independent": control["independent"],
                "observed_passed": observation.get("observed_passed") if observation else None,
                "control_passed": observation.get("passed") if observation else None,
                "reason": observation.get("reason") if observation else None,
                "error": observation.get("error") if observation else None,
            }
        )
    target_identity = (candidate or {}).get("target_identity", {})
    target_config = target_identity.get("config", {}) if isinstance(target_identity, dict) else {}
    review_blockers = [
        {
            "area": event["area"],
            "decision": event["decision"],
            "subject": event["subject"],
            "rationale": event["rationale"],
        }
        for event in verification["review"].get("blockers", [])
    ]
    report = {
        "schema_version": 1,
        "kind": "acceptance-report",
        "created_at": timestamp(),
        "change": project.change,
        "title": project.contract.title,
        "decision": verification["decision"],
        "criteria_digest": project.criteria_digest(),
        "bundle_digest": project.bundle_digest(),
        "review": verification["review"],
        "blockers": [*verification["gaps"], *review_blockers],
        "evidence": {
            "audit": _evidence_summary(audit, verification["audit"], fresh_run_ids),
            "candidate": _evidence_summary(candidate, verification["candidate"], fresh_run_ids),
            "baseline": {**verification["baseline"], "origin": "saved"},
        },
        "application": {
            "target": (candidate or {}).get("target"),
            "target_digest": (candidate or {}).get("target_digest"),
            "configured_version": target_config.get("version"),
            "revision": application_revision
            or target_config.get("version")
            or (candidate or {}).get("target_digest"),
        },
        "grader_configuration": packet["metrics"],
        "acceptance_profile": packet["acceptance_profile"],
        "cases": cases,
        "controls": controls,
        "limitation": (
            "Passing declared controls does not prove universal grader reliability; "
            "it demonstrates only the recorded known examples."
        ),
    }
    report["markdown"] = render_report(report)
    return report


def render_report(report: dict) -> str:
    lines = [
        f"# EDD acceptance report: {report['title']}",
        "",
        f"Decision: **{report['decision']}**  ",
        f"Change: `{report['change']}`  ",
        f"Criteria: `{report['criteria_digest']}`  ",
        f"Application revision: `{report['application']['revision']}`",
        "",
        "## Review and blockers",
        "",
        f"- Domain approval: {report['review']['domain']['status']}",
        f"- Technical validation: {report['review']['technical']['status']}",
    ]
    if report["blockers"]:
        for blocker in report["blockers"]:
            value = blocker if isinstance(blocker, str) else blocker["rationale"]
            lines.append(f"- Blocker: {value}")
    else:
        lines.append("- No unresolved blockers.")
    lines.extend(["", "## Evidence", ""])
    for name in ("audit", "candidate", "baseline"):
        evidence = report["evidence"][name]
        lines.append(
            f"- {name.title()}: {evidence.get('decision', evidence.get('status'))}; "
            f"origin `{evidence.get('origin', 'saved')}`; record `{evidence.get('id', 'none')}`"
        )
    lines.extend(["", "## Expected versus observed", ""])
    for case in report["cases"]:
        lines.extend(
            [
                f"### `{case['id']}`",
                "",
                case["expected_behavior"] or "_Expected behavior missing._",
                "",
            ]
        )
        if not case["observations"]:
            lines.append("No candidate observation was recorded.")
        for observation in case["observations"]:
            lines.append(
                f"- `{observation['requirement_id']}`: "
                f"{'PASS' if observation['passed'] else 'FAIL'} — "
                f"observed `{observation['actual_output']}`"
            )
    lines.extend(["", "## Control results", ""])
    for control in report["controls"]:
        result = (
            "not executed"
            if control["control_passed"] is None
            else "matched label"
            if control["control_passed"]
            else "did not match label"
        )
        lines.append(
            f"- `{control['id']}` ({control['expected']}): {result}; "
            f"known example: {control['rationale']}"
        )
    lines.extend(["", f"> {report['limitation']}", ""])
    return "\n".join(lines)


def write_report_bundle(project: Project, directory: str, report: dict) -> dict[str, str]:
    path = safe_path(project.root, directory, must_exist=False)
    if path.exists() and not path.is_dir():
        raise ProjectError("Report output must be a directory")
    path.mkdir(parents=True, exist_ok=True)
    outputs = {
        "markdown": path / "report.md",
        "json": path / "report.json",
    }
    payloads = {
        "markdown": report["markdown"].encode(),
        "json": (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(),
    }
    for name, output_path in outputs.items():
        if output_path.is_symlink():
            raise ProjectError("Refusing symlink report path")
        fd, temporary = tempfile.mkstemp(prefix=".edd-report-", dir=path)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payloads[name])
                stream.flush()
                os.fsync(stream.fileno())
            if output_path.is_symlink():
                raise ProjectError("Refusing symlink report path")
            os.replace(temporary, output_path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return {
        name: output_path.relative_to(project.root).as_posix()
        for name, output_path in outputs.items()
    }
