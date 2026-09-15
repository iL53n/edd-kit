"""Terminal setup and deterministic evaluation. Agent skills author feature semantics."""

import argparse
import difflib
import importlib.metadata
import json
import os
import platform
import re
import sys
import tempfile
from pathlib import Path

from . import __version__
from .engine import Workflow
from .evidence import read_record
from .project import ProjectError, changes_directory, project_root, safe_path
from .scaffold import init_project, prepare_change, sync_skills

EXIT = {"PASS": 0, "FAIL": 1, "ERROR": 2, "INCONCLUSIVE": 3}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ProjectError(message)


def parser() -> argparse.ArgumentParser:
    result = Parser(
        description="EDD Kit: Prepare → Build → Check. Agents author; this CLI validates and runs."
    )
    result.add_argument("--version", action="version", version=f"edd {__version__}")
    result.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Project root (default: current directory)"
    )
    result.add_argument("--json", action="store_true", help="Machine-readable JSON on stdout")
    result.add_argument("--verbose", action="store_true", help="Show detailed human output")
    commands = result.add_subparsers(dest="command", required=True)
    for name, help_text in {
        "init": "Initialize project and install coding-agent skills",
        "prepare": "Scaffold an eval draft; use your agent to author domain behavior",
        "baseline-unavailable": "Record why a meaningful baseline is unavailable",
        "sync": "Preview or refresh managed skills, preserving local edits",
        "doctor": "Diagnose runtime and backend installation",
        "inspect": "Load and validate a native suite, showing execution work before running",
        "review": "Record an explicitly authorized review of current criteria",
        "audit": "Evaluate graders against reviewed positive and negative controls",
        "run": "Run an application, stub, or reference target",
        "verify": "Verify current review, audit, and candidate acceptance evidence",
        "status": "Show durable readiness and acceptance state",
        "report": "Read a recorded run and its per-observation evidence",
        "check": "Run fresh audit and candidate acceptance, then verify",
        "demo": "Run the isolated offline cancellation walkthrough",
    }.items():
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        command.add_argument("--root", type=Path, default=argparse.SUPPRESS)
        command.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS)
        if name in {"init", "sync"}:
            command.add_argument("--agent", choices=["codex", "claude", "none"], default="codex")
        if name == "demo":
            command.add_argument(
                "example",
                nargs="?",
                choices=["cancellation"],
                default="cancellation",
                help="Bundled demonstration to run (default: cancellation)",
            )
        if name == "sync":
            command.add_argument(
                "--apply", action="store_true", help="Apply safe updates (default: preview)"
            )
        if name not in {"init", "sync", "doctor", "demo"}:
            command.add_argument("change", nargs="?" if name in {"status", "check"} else None)
        if name == "prepare":
            command.add_argument(
                "--brief", required=True, help="Intended behavior in natural language"
            )
            command.add_argument(
                "--template", choices=["starter", "cancellation"], default="starter"
            )
        if name == "baseline-unavailable":
            command.add_argument("--reason", required=True)
        if name == "review":
            command.add_argument(
                "--write", action="store_true", help="Write the deterministic REVIEW.md packet"
            )
            command.add_argument("--area", choices=["domain", "technical"])
            command.add_argument(
                "--decision", choices=["approve", "request_changes", "needs_discussion"]
            )
            command.add_argument(
                "--subject", help="Optional requirement:ID, case:ID, or control:ID"
            )
            command.add_argument("--by", help="Person explicitly reviewing the current criteria")
            command.add_argument("--note", help="Decision context; this is a local declaration")
            command.add_argument(
                "--approve-controls",
                metavar="all",
                help="Deprecated; use --area technical --decision approve",
            )
            command.add_argument(
                "--approve-control",
                action="append",
                default=[],
                metavar="ID",
                help="Deprecated; record technical feedback with --subject control:ID",
            )
            command.add_argument(
                "--criteria-digest",
                help="Reject approval if criteria changed after the review packet",
            )
        if name in {"inspect", "audit", "run"}:
            command.add_argument("--profile", choices=["dev", "acceptance"], default="acceptance")
        if name in {"audit", "run", "check"}:
            command.add_argument(
                "--allow-paid",
                action="store_true",
                help="Allow configured model judges within the declared work/cost policy",
            )
        if name in {"run", "check"}:
            command.add_argument("--target")
        if name == "run":
            command.add_argument("--stage", choices=["baseline", "candidate"], default="candidate")
        if name == "report":
            command.add_argument("--run", help="Recorded run ID (default: newest)")
            command.add_argument(
                "--acceptance", action="store_true", help="Consolidate current acceptance evidence"
            )
            command.add_argument("--output-dir", help="Write report.md and report.json here")
            command.add_argument(
                "--revision", help="Application source revision shown in the report"
            )
        if name == "check":
            command.add_argument("--report-dir", help="Write report.md and report.json here")
            command.add_argument(
                "--revision", help="Application source revision shown in the report"
            )
    return result


def _doctor(root: Path) -> dict:
    try:
        backend = importlib.metadata.version("deepeval")
    except importlib.metadata.PackageNotFoundError:
        backend = None
    problems = []
    if os.name != "posix":
        problems.append("Execution requires Linux or macOS")
    if backend != "4.2.3":
        problems.append("Reinstall the complete tool: uv tool install --reinstall edd-kit")
    return {
        "command": "doctor",
        "decision": "ERROR" if problems else "PASS",
        "edd": __version__,
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "deepeval": backend,
        "project_initialized": (root / "edd.toml").is_file(),
        "next_steps": problems,
        "cloud_account_required": False,
    }


def dispatch(args) -> dict:
    root = project_root(args.root)
    name = args.command
    if name == "init":
        result = init_project(root, args.agent)
        invocation = "$edd-prepare" if args.agent == "codex" else "/edd-prepare"
        return {
            **result,
            "command": name,
            "environment": _doctor(root),
            "restart_required": args.agent != "none"
            and bool(result["created"] + result["updated"]),
            "next_steps": [
                f"AI chat: {invocation} <describe your feature>"
                if args.agent != "none"
                else "Terminal: edd prepare <change> --brief '<behavior>'; author its native suite"
            ],
        }
    if name == "prepare":
        return {
            **prepare_change(root, args.change, args.brief, args.template),
            "command": name,
            "authoring_required": args.template == "starter",
            "next_steps": [
                "Review the brief; author domain cases, metrics, controls and the target adapter",
                f"Terminal: edd inspect {args.change} --json",
            ],
        }
    if name == "sync":
        return {**sync_skills(root, args.agent, preview=not args.apply), "command": name}
    if name == "doctor":
        return _doctor(root)
    if name == "demo":
        return _demo()
    if name == "status" and args.change is None:
        directory = changes_directory(root)
        changes = (
            sorted(path.parent.name for path in directory.glob("*/contract.json"))
            if directory.exists()
            else []
        )
        statuses = [Workflow(root, change).status() for change in changes]
        summary = {
            phase: sum(item["workflow"]["phase"] == phase for item in statuses)
            for phase in ("prepare", "build", "check", "complete")
        }
        return {
            "schema_version": 1,
            "command": name,
            "changes": statuses,
            "summary": summary,
            "actions": (
                [
                    {
                        "id": "prepare-change",
                        "actor": "cli",
                        "command": "edd prepare <change> --brief '<behavior>'",
                    }
                ]
                if not statuses
                else []
            ),
            "next_steps": (
                ["Prepare the first change with edd prepare <change> --brief '<behavior>'"]
                if not statuses
                else ["Choose a change explicitly; EDD does not infer one from a Git branch"]
            ),
        }
    workflow = Workflow(root, _known_change(root, args.change))
    if name == "inspect":
        result = workflow.inspect(profile=args.profile)
        return {
            **result,
            "scope": "configuration-only",
            "decision": "ERROR" if result.get("execution_errors") else "PASS",
            "note": "Pipeline inspection is not grader validation or feature acceptance",
        }
    if name == "review":
        recording = bool(
            args.area
            or args.decision
            or args.subject
            or args.by
            or args.note
            or args.approve_controls
            or args.approve_control
        )
        if args.write:
            if recording:
                raise ProjectError("--write cannot be combined with a review decision")
            path = workflow.write_review_packet()
            return {
                "schema_version": 2,
                "kind": "review-packet-written",
                "change": workflow.change,
                "path": str(path.relative_to(root)),
                "criteria_digest": workflow.project.criteria_digest(),
            }
        if not recording:
            return workflow.review_packet()
        if args.approve_controls or args.approve_control:
            raise ProjectError(
                "Control approval no longer edits criteria; use --area technical --decision approve"
            )
        if not all((args.area, args.decision, args.by, args.note, args.criteria_digest)):
            raise ProjectError(
                "A decision requires --area, --decision, --by, --note, and --criteria-digest"
            )
        return workflow.record_review(
            area=args.area,
            decision=args.decision,
            reviewer=args.by,
            rationale=args.note,
            criteria_digest=args.criteria_digest,
            subject=args.subject,
        )
    if name == "baseline-unavailable":
        return workflow.baseline_unavailable(args.reason)
    if name == "audit":
        return workflow.audit(profile=args.profile, allow_paid=args.allow_paid)
    if name == "run":
        target = args.target or _infer_target(workflow, stage=args.stage)
        return workflow.run(
            target, stage=args.stage, profile=args.profile, allow_paid=args.allow_paid
        )
    if name == "verify":
        return workflow.verify()
    if name == "status":
        return workflow.status()
    if name == "report":
        if args.acceptance:
            if args.run:
                raise ProjectError("Choose --acceptance or --run, not both")
            result = workflow.acceptance_report(application_revision=args.revision)
            if args.output_dir:
                result["report_paths"] = workflow.write_acceptance_report(args.output_dir, result)
            return result
        if args.output_dir or args.revision:
            raise ProjectError("--output-dir and --revision require --acceptance")
        project = workflow.project
        directory = safe_path(
            root, str((project.state / "runs").relative_to(root)), must_exist=False
        )
        if args.run:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run):
                raise ProjectError("Invalid run ID")
            path = directory / f"{args.run}.json"
        else:
            matches = sorted(directory.glob("*.json"))
            if not matches:
                raise ProjectError("No recorded runs for this change")
            path = matches[-1]
        return read_record(path)
    if name == "check":
        target = args.target or _infer_target(workflow, stage="candidate")
        return workflow.check(
            target,
            allow_paid=args.allow_paid,
            report_dir=args.report_dir,
            application_revision=args.revision,
        )
    raise ProjectError("Unknown command")


def _known_change(root: Path, change: str | None) -> str:
    directory = changes_directory(root)
    choices = sorted(path.parent.name for path in directory.glob("*/contract.json"))
    if change is None:
        if len(choices) == 1:
            return choices[0]
        if not choices:
            raise ProjectError("No prepared changes; run edd prepare <change> --brief '<behavior>'")
        raise ProjectError(f"Change is ambiguous; choose one explicitly: {', '.join(choices)}")
    contract = directory / change / "contract.json"
    if contract.is_file():
        return change
    matches = difflib.get_close_matches(change, choices, n=3, cutoff=0.45)
    suggestion = f" Did you mean: {', '.join(matches)}?" if matches else ""
    available = f" Available changes: {', '.join(choices)}." if choices else ""
    raise ProjectError(f"Unknown change: {change}.{suggestion}{available}".replace("..", "."))


def _infer_target(workflow: Workflow, *, stage: str) -> str:
    targets = workflow.project.contract.targets
    if stage == "baseline":
        preferred = [
            name for name, target in targets.items() if target.kind in {"stub", "reference"}
        ]
        eligible = (
            preferred
            if preferred
            else [name for name, target in targets.items() if target.kind == "application"]
        )
    else:
        eligible = [name for name, target in targets.items() if target.kind == "application"]
    if len(eligible) == 1:
        return eligible[0]
    choices = ", ".join(eligible) if eligible else "none"
    examples = "; ".join(
        f"edd run {workflow.change} --target {name} --stage {stage}" for name in eligible
    )
    suffix = f" Try: {examples}" if examples else ""
    raise ProjectError(f"Target is ambiguous; eligible {stage} targets: {choices}.{suffix}")


def _demo() -> dict:
    with tempfile.TemporaryDirectory(prefix="edd-demo-") as directory:
        root = Path(directory)
        init_project(root, "none")
        prepare_change(root, "cancellation", "Cancel owned orders safely", "cancellation")
        workflow = Workflow(root, "cancellation")
        audit = workflow.audit()
        candidate = workflow.run("candidate", stage="candidate")
        noop = workflow.run("noop", stage="candidate")
        wrong_owner = workflow.run("wrong-owner", stage="candidate")
    demonstrated = (
        audit.get("decision") == "PASS"
        and candidate.get("decision") == "PASS"
        and noop.get("decision") == "FAIL"
        and wrong_owner.get("decision") == "FAIL"
    )
    return {
        "schema_version": 1,
        "command": "demo",
        "demonstrated": demonstrated,
        "checks": {
            "grader_audit": audit.get("decision"),
            "working_candidate": candidate.get("decision"),
            "fabricated_success": "DETECTED" if noop.get("decision") == "FAIL" else "MISSED",
            "wrong_owner_change": (
                "DETECTED" if wrong_owner.get("decision") == "FAIL" else "MISSED"
            ),
        },
        "note": (
            "Synthetic graders caught both seeded defects. This walkthrough is not production "
            "acceptance evidence."
            if demonstrated
            else "The offline walkthrough did not produce its expected results."
        ),
    }


def human_report(data: dict, *, verbose: bool = False) -> str:
    if data.get("command") == "init":
        environment = data.get("environment", {})
        lines = ["EDD init — COMPLETE", f"Agent integration: {data.get('agent', 'none')}"]
        lines.append(
            "Environment: ready"
            if environment.get("decision") == "PASS"
            else "Environment: setup required (run edd doctor)"
        )
        changed = len(data.get("created", [])) + len(data.get("updated", []))
        lines.append(f"Installed or updated: {changed} file(s)")
        if data.get("restart_required"):
            lines.append("Restart your coding-agent session so the installed skills are visible.")
        if data.get("next_steps"):
            lines.append(f"Next: {data['next_steps'][0]}")
        return "\n".join(lines)
    if data.get("command") == "doctor":
        lines = [f"EDD doctor — {data['decision']}"]
        lines.append(f"Python: {data['python']} ({data['python_executable']})")
        lines.append(f"DeepEval: {data.get('deepeval') or 'not installed'}")
        lines.append(
            f"Project: {'initialized' if data.get('project_initialized') else 'not initialized'}"
        )
        lines.append("Cloud account: not required")
        lines.extend(f"Next: {step}" for step in data.get("next_steps", []))
        return "\n".join(lines)
    if data.get("command") == "demo":
        lines = ["EDD demo — COMPLETE" if data.get("demonstrated") else "EDD demo — ATTENTION"]
        lines.extend(
            f"  {name.replace('_', ' ').title()}: {value}" for name, value in data["checks"].items()
        )
        lines.append(data["note"])
        return "\n".join(lines)
    if data.get("kind") == "review-packet":
        return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", data["markdown"])
    if data.get("kind") == "review-decision":
        event = data["event"]
        return (
            f"EDD {data['change']} — REVIEW DECISION RECORDED\n"
            f"{event['area'].title()}: {event['decision']} by {event['reviewer']}\n"
            f"Criteria: {data['criteria_digest']}"
        )
    if data.get("kind") == "acceptance-report":
        return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", data["markdown"])
    if "workflow" in data:
        workflow = data["workflow"]
        heading = f"EDD {data['change']} — {workflow['phase'].upper()}"
        lines = [heading, workflow["summary"]]
        symbols = {"complete": "✓", "current": "✓", "missing": "○", "stale": "↻", "attention": "!"}
        progress = " · ".join(
            f"{symbols.get(item['status'], '○')} {item['label']}" for item in workflow["checklist"]
        )
        lines.append(f"Progress: {progress}")
        if data.get("actions"):
            action = data["actions"][0]
            next_value = (
                action.get("chat")
                if action.get("actor") == "agent" and action.get("chat")
                else action.get("command") or action.get("chat")
            )
            lines.append(f"Next ({action['actor']}): {action['label']}")
            if next_value:
                lines.append(f"  {next_value}")
        if not verbose:
            lines.append(f"Details: edd status {data['change']} --verbose")
            return "\n".join(lines)
        lines.append(f"Evidence decision: {data['decision']}")
        for diagnostic in data.get("diagnostics", []):
            lines.append(f"  [{diagnostic['code']}] {diagnostic['message']}")
        hidden = {"workflow", "actions", "diagnostics"}
        data = {key: value for key, value in data.items() if key not in hidden}
        detail = _legacy_human_report(data).splitlines()[1:]
        return "\n".join([*lines, *detail])
    if "changes" in data:
        lines = ["EDD project — STATUS"]
        if not data["changes"]:
            lines.append("No prepared changes")
            if data.get("actions"):
                lines.append(f"Next: {data['actions'][0]['command']}")
        for phase in ("prepare", "build", "check", "complete"):
            matching = [
                item for item in data["changes"] if item.get("workflow", {}).get("phase") == phase
            ]
            if not matching:
                continue
            lines.append(phase.upper())
            for item in matching:
                workflow = item["workflow"]
                lines.append(f"  {item['change']}: {workflow['summary']}")
                if item.get("actions"):
                    action = item["actions"][0]
                    next_value = (
                        action.get("chat")
                        if action.get("actor") == "agent" and action.get("chat")
                        else action.get("command") or action.get("chat") or action["label"]
                    )
                    lines.append(f"    Next: {next_value}")
        return "\n".join(lines)
    return _legacy_human_report(data)


def _legacy_human_report(data: dict) -> str:
    lines = [
        f"EDD {data.get('change', data.get('command', ''))}: {data.get('decision', 'complete')}"
    ]
    if data.get("scope") == "configuration-only":
        lines[0] = f"EDD {data['change']}: Configuration only — {data['decision']}"
    if data.get("note"):
        lines.append(data["note"])
    if "ready_to_build" in data:
        lines.append(f"Ready to build: {'yes' if data['ready_to_build'] else 'no'}")
    if data.get("error"):
        lines.append(data["error"])
    if data.get("authoring_required"):
        lines.append("Draft scaffold created. Domain authoring and review are still required.")
    for key in ("created", "updated", "preserved", "conflicts"):
        if data.get(key):
            lines.append(f"{key.capitalize()}: {len(data[key])} file(s)")
    for key in ("review", "audit", "baseline", "candidate"):
        value = data.get(key)
        if isinstance(value, dict):
            label = f"{key.capitalize()}: {value.get('status', '')} {value.get('decision', '')}"
            lines.append(label.rstrip())
    if "expected" in data:
        lines.append(
            f"Observations: {data['completed']}/{data['expected']}; errors: {data['errors']}"
        )
    if "controls" in data:
        validation = sum(item.get("partition") == "validation" for item in data["controls"])
        calibration = sum(item.get("partition") == "calibration" for item in data["controls"])
        lines.append(
            f"Controls: {validation} validation; {calibration} calibration excluded from audit"
        )
    for requirement, result in data.get("requirements", {}).items():
        lines.append(
            f"  {requirement}: {result['passed']} passed, {result['failed']} failed, "
            f"{result['errors']} errors"
        )
    failures = [
        row
        for row in data.get("observations", [])
        if row.get("error") or row.get("passed") is False
    ]
    for row in failures[:10]:
        reason = row.get("error") or row.get("reason") or "failed"
        lines.append(f"  {row['case_id']} / {row['requirement_id']}: {reason}")
    for key in ("gaps", "execution_errors", "integrity_errors", "next_steps"):
        lines.extend(f"  {message}" for message in data.get(key, []))
    if data.get("kind") == "baseline" and data.get("decision") == "FAIL":
        lines.append(
            "Expected feature failures can be a valid baseline; inspect evidence before building."
        )
    if data.get("id"):
        lines.append(f"Record: {data['id']}")
    if "changes" in data:
        lines.extend(f"  {item['change']}: {item['decision']}" for item in data["changes"])
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", "\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    try:
        args = parser().parse_args(argv)
        as_json = args.json
        data = dispatch(args)
        if args.command == "demo":
            code = 0 if data.get("demonstrated") else 2
        elif args.command in {"doctor", "inspect", "audit", "run", "verify", "check"}:
            code = EXIT.get(data.get("decision", ""), 0)
        else:
            code = 0
    except KeyboardInterrupt:
        data = {
            "decision": "ERROR",
            "error": "Interrupted; incomplete work is not acceptance evidence",
        }
        code = 130
    except (ValueError, OSError, ImportError) as exc:
        data = {"decision": "ERROR", "error": str(exc)}
        code = 2
    print(
        json.dumps(data, indent=2, sort_keys=True, allow_nan=False)
        if as_json
        else human_report(data, verbose=args.verbose)
    )
    return code
