"""Consolidated human and machine-readable acceptance evidence."""

from __future__ import annotations

import json
import os
import tempfile

from .evidence import timestamp
from .project import Project, ProjectError, safe_path


def build_measurement_report(
    project: Project,
    *,
    run: dict,
    comparison: dict | None,
    application_revision: str | None,
) -> dict:
    observations: dict[str, list[dict]] = {}
    for row in run.get("observations", []):
        observations.setdefault(row["case_id"], []).append(
            {
                key: row.get(key)
                for key in (
                    "id",
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
    cases = [
        {
            "id": case["case_id"],
            "requirements": case.get("requirements", []),
            "input": case.get("input"),
            "description": case.get("description"),
            "expected_behavior": case.get("expected_behavior"),
            "reference_output": case.get("reference_output"),
            "acceptable_alternatives": case.get("acceptable_alternatives", []),
            "unacceptable_behaviors": case.get("unacceptable_behaviors", []),
            "source": case.get("source", "unknown"),
            "expectation_source": case.get("expectation_source", "unknown"),
            "deferred_reason": case.get("deferred_reason"),
            "observations": observations.get(case["case_id"], []),
        }
        for case in run.get("cases", [])
    ]
    if run.get("execution_errors") or run.get("integrity_errors") or run.get("errors"):
        execution_status = "ERROR"
    elif run.get("missing") or run.get("gaps"):
        execution_status = "INCONCLUSIVE"
    else:
        execution_status = "COMPLETE"
    target_config = run.get("target_identity", {}).get("config", {})
    saved_contract = run.get("bundle_identity", {}).get("criteria", {}).get("contract", {})
    report = {
        "schema_version": 1,
        "kind": "measurement-report",
        "created_at": timestamp(),
        "change": project.change,
        "title": saved_contract.get("title", project.contract.title),
        "execution_status": execution_status,
        "behavior_decision": run.get("decision"),
        "run_id": run["id"],
        "run_kind": run["kind"],
        "profile": run["profile"],
        "criteria_digest": run["criteria_digest"],
        "bundle_digest": run["bundle_digest"],
        "target": run.get("target"),
        "target_digest": run.get("target_digest"),
        "application_revision": application_revision
        or target_config.get("version")
        or run.get("target_digest"),
        "counts": run.get("counts", {}),
        "expected": run.get("expected", 0),
        "completed": run.get("completed", 0),
        "scenario_count": len(cases),
        "deferred_count": sum(bool(case["deferred_reason"]) for case in cases),
        "requirements": run.get("requirements", {}),
        "observed_cost_usd": run.get("observed_cost_usd"),
        "gaps": run.get("gaps", []),
        "execution_errors": run.get("execution_errors", []),
        "cases": cases,
        "comparison": comparison,
        "limitation": (
            "This is a measurement over the recorded scenarios, not product acceptance or an "
            "estimate of production reliability."
        ),
    }
    report["markdown"] = render_measurement_report(report)
    return report


def render_measurement_report(report: dict) -> str:
    def cell(value: object) -> str:
        shown = "unknown" if value is None or value == "" else value
        return str(shown).replace("|", "\\|").replace("\n", " ")

    lines = [
        f"# EDD measurement: {report['title']}",
        "",
        f"Execution: **{report['execution_status']}**  ",
        f"Observed behavior: **{report['behavior_decision']}**  ",
        f"Run: `{report['run_id']}`  ",
        f"Target: `{report['target']}`  ",
        f"Scenarios: {report['scenario_count']} ({report['deferred_count']} deferred)  ",
        f"Observations: {report['completed']}/{report['expected']}",
        "",
        "## Scenario inventory",
        "",
        "| Scenario | Source | Expectation source | Result |",
        "| --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        if case["deferred_reason"]:
            result = "deferred"
        elif any(row.get("error") for row in case["observations"]):
            result = "error"
        elif any(row.get("passed") is False for row in case["observations"]):
            result = "fail"
        elif case["observations"] and all(
            row.get("passed") is True for row in case["observations"]
        ):
            result = "pass"
        else:
            result = "incomplete"
        lines.append(
            f"| `{cell(case['id'])}` | {cell(case['source'])} | "
            f"{cell(case['expectation_source'])} | {result} |"
        )
    lines.extend(
        [
            "",
            "## Problems and changes",
            "",
        ]
    )
    problems = []
    for case in report["cases"]:
        failed = [
            row for row in case["observations"] if row.get("error") or row.get("passed") is False
        ]
        if failed or case["deferred_reason"]:
            problems.append((case, failed))
    if not problems:
        lines.append("No failed or deferred scenarios in this run.")
    for case, failures in problems:
        lines.extend(
            [
                "",
                f"### `{case['id']}`",
                "",
                case["expected_behavior"] or "_No expected behavior recorded._",
            ]
        )
        if case["deferred_reason"]:
            lines.append(f"- Deferred: {case['deferred_reason']}")
        for row in failures:
            outcome = row.get("error") or row.get("reason") or "check failed"
            lines.append(f"- `{row['requirement_id']}`: {outcome}")
            if row.get("actual_output") is not None:
                lines.append(f"  Observed: `{row['actual_output']}`")
    comparison = report.get("comparison")
    if comparison:
        lines.extend(["", "## Comparison", ""])
        if comparison["status"] == "comparable":
            for requirement, delta in comparison.get("deltas", {}).items():
                lines.append(f"- `{requirement}`: {delta:+.3f}")
            if not comparison.get("changed_observations"):
                lines.append("- No observation result changed.")
        else:
            lines.append(f"- Unavailable: {comparison['reason']}")
        changes = comparison.get("case_changes", {})
        for name in ("added", "removed", "changed"):
            if changes.get(name):
                lines.append(f"- Cases {name}: {', '.join(changes[name])}")
    if report["gaps"] or report["execution_errors"]:
        lines.extend(["", "## Incomplete evidence", ""])
        lines.extend(f"- {value}" for value in [*report["gaps"], *report["execution_errors"]])
    lines.extend(["", f"> {report['limitation']}", ""])
    return "\n".join(lines)


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
