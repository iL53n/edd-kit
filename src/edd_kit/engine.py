"""Persistent behavior measurements and the optional strict acceptance workflow."""

import contextlib
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .decisions import decide
from .evidence import new_id, project_lock, read_record, redact, timestamp, write_record
from .models import Profile
from .project import Project, ProjectError, digest, project_root, safe_path
from .review import (
    load_review,
    packet_content,
    packet_path,
    packet_status,
    record_decision,
    render_markdown,
    review_state,
    revision_diff,
    stored_packet_status,
)


class Workflow:
    def __init__(self, root: Path, change: str):
        self.root = project_root(root)
        self.change = change

    @property
    def project(self) -> Project:
        # Re-read on each operation so a resumed workflow sees manual edits.
        return Project(self.root, self.change)

    def inspect(self, *, profile: str = "acceptance") -> dict:
        from .execution import execute

        project = self.project
        result = execute(project, "inspect", profile=profile)
        self._redact_diagnostics(project, result)
        response = {
            "change": self.change,
            "criteria_digest": project.criteria_digest(),
            "bundle_digest": project.bundle_digest(),
            "title": project.contract.title,
            "targets": {key: value.kind for key, value in project.contract.targets.items()},
            **result,
        }
        content = packet_content(project, response)
        content["revision_diff"] = revision_diff(project, content)
        expected = render_markdown(content)
        response["review_packet_status"] = packet_status(project, expected)
        if response["review_packet_status"] != "current":
            response["gaps"] = [
                *response.get("gaps", []),
                f"REVIEW.md is {response['review_packet_status']}; run edd review "
                f"{self.change} --write",
            ]
        return response

    def review_packet(self) -> dict:
        """Return a review-oriented, read-only summary of the current criteria."""
        project = self.project
        inspection = self.inspect()
        status = self.status()
        packet = packet_content(project, inspection)
        packet["revision_diff"] = revision_diff(project, packet)
        packet.update(
            {
                "audit": status["audit"],
                "baseline": status["baseline"],
                "review_packet_status": inspection["review_packet_status"],
                "note": "Reviewing this packet does not itself record approval",
            }
        )
        packet["markdown"] = render_markdown(packet)
        return packet

    def write_review_packet(self) -> Path:
        """Write the deterministic specialist packet next to the canonical criteria."""
        project = self.project
        path = packet_path(project)
        self._write_bytes(path, self.review_packet()["markdown"].encode("utf-8"))
        return path

    def record_review(
        self,
        *,
        area: str,
        decision: str,
        reviewer: str,
        rationale: str,
        criteria_digest: str,
        subject: str | None = None,
    ) -> dict:
        if area not in {"domain", "technical"}:
            raise ProjectError("Review area must be domain or technical")
        if decision not in {"approve", "request_changes", "needs_discussion"}:
            raise ProjectError("Unknown review decision")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (reviewer, rationale, criteria_digest)
        ):
            raise ProjectError("Review requires reviewer, rationale, and criteria digest")
        project = self.project
        with project_lock(project.root, project.state):
            packet = self.review_packet()
            if criteria_digest != packet["criteria_digest"]:
                raise ProjectError(
                    "Criteria changed after the review packet was created; run edd review again"
                )
            if packet["review_packet_status"] != "current":
                raise ProjectError("Commit the current REVIEW.md before recording review")
            if area == "domain" and decision == "approve" and packet.get("review_gaps"):
                raise ProjectError(
                    "Domain approval requires complete specialist review descriptions"
                )
            valid_subjects = {
                *(f"requirement:{value}" for value in packet["requirements"]),
                *(f"case:{value['case_id']}" for value in packet["cases"]),
                *(f"control:{value['id']}" for value in packet["controls"]),
            }
            if subject is not None and subject not in valid_subjects:
                raise ProjectError(f"Unknown review subject: {subject}")
            if subject is not None:
                kind = subject.split(":", 1)[0]
                if area == "domain" and kind not in {"requirement", "case"}:
                    raise ProjectError("Domain feedback must reference a requirement or case")
                if area == "technical" and kind not in {"requirement", "control"}:
                    raise ProjectError("Technical feedback must reference a requirement or control")
            if area == "technical" and decision == "approve":
                status = self.status()
                if status["review"].get("domain", {}).get("status") != "approved":
                    raise ProjectError("Technical approval requires current domain approval")
                audit = status["audit"]
                if audit.get("status") != "current" or audit.get("decision") != "PASS":
                    raise ProjectError("Technical approval requires a current passing audit")
            review_path = project.directory / "review.json"
            original_review = review_path.read_bytes() if review_path.exists() else None
            event = None
            history_path = None
            try:
                event = record_decision(
                    project,
                    packet=packet,
                    area=area,
                    decision=decision,
                    reviewer=reviewer,
                    rationale=rationale,
                    subject=subject,
                )
                history_path = project.state / "reviews" / f"{event['id']}.json"
                write_record(history_path, event)
            except Exception:
                if original_review is None:
                    with contextlib.suppress(FileNotFoundError):
                        review_path.unlink()
                else:
                    self._write_bytes(review_path, original_review)
                if history_path is not None:
                    with contextlib.suppress(FileNotFoundError):
                        history_path.unlink()
                raise
            assert event is not None
        return {
            "schema_version": 2,
            "kind": "review-decision",
            "change": self.change,
            "criteria_digest": criteria_digest,
            "event": event,
            "review": review_state(self.project),
        }

    @staticmethod
    def _write_bytes(path: Path, payload: bytes) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".edd-review-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)

    def audit(self, *, profile: str = "acceptance", allow_paid: bool = False) -> dict:
        return self._evaluate("audit", profile=profile, allow_paid=allow_paid)

    def baseline_unavailable(self, reason: str) -> dict:
        """Record an explicit workflow choice, never an invented baseline score."""
        if not isinstance(reason, str) or not reason.strip():
            raise ProjectError("An unavailable baseline requires a meaningful reason")
        project = self.project
        with project_lock(project.root, project.state):
            identity = project.bundle_identity()
            record: dict[str, Any] = {
                "schema_version": 1,
                "id": new_id(),
                "created_at": timestamp(),
                "finished_at": timestamp(),
                "kind": "baseline-unavailable",
                "change": self.change,
                "profile": "acceptance",
                "reason": reason.strip(),
                "bundle_identity": identity,
                "bundle_digest": digest(identity),
                "criteria_digest": project.criteria_digest(),
                "decision": "UNAVAILABLE",
                "source_identity": self._source_identity(project, identity, None),
            }
            write_record(project.state / "runs" / f"{record['id']}.json", record)
        return record

    def run(
        self,
        target: str,
        *,
        stage: Literal["baseline", "candidate"] = "candidate",
        profile: str = "acceptance",
        allow_paid: bool = False,
    ) -> dict:
        if stage not in {"baseline", "candidate"}:
            raise ProjectError("Run stage must be baseline or candidate")
        return self._evaluate(stage, target=target, profile=profile, allow_paid=allow_paid)

    def _evaluate(
        self, kind: str, *, target: str | None = None, profile: str, allow_paid: bool
    ) -> dict:
        from .execution import execute

        project = self.project
        if profile not in project.contract.profiles:
            raise ProjectError("Unknown execution profile")
        with project_lock(project.root, project.state):
            bundle_identity = project.bundle_identity()
            before = digest(bundle_identity)
            target_identity = project.target_identity(target) if target else None
            target_before = project.target_digest(target) if target else None
            record: dict[str, Any] = {
                "schema_version": 1,
                "id": new_id(),
                "created_at": timestamp(),
                "kind": kind,
                "change": self.change,
                "profile": profile,
                "bundle_digest": before,
                "bundle_identity": bundle_identity,
                "criteria_digest": project.criteria_digest(),
                "target": target,
                "target_kind": project.contract.targets[target].kind if target else None,
                "target_digest": target_before,
                "target_identity": target_identity,
                "execution_policy": project.contract.profiles[profile].model_dump(),
                "source_identity": self._source_identity(project, bundle_identity, target_identity),
            }
            result = execute(
                project,
                "audit" if kind == "audit" else "run",
                profile=profile,
                target=target,
                allow_paid=allow_paid,
            )
            record.update(result)
            record.setdefault("expected_ids", [])
            record.setdefault("observations", [])
            record.setdefault("gaps", [])
            record.setdefault("execution_errors", [])
            record["inspection_gaps"] = list(record["gaps"])
            try:
                current = self.project
                if current.bundle_digest() != before:
                    record["execution_errors"].append("Evaluation bundle changed during execution")
                if target and current.target_digest(target) != target_before:
                    record["execution_errors"].append("Target changed during execution")
            except (ProjectError, OSError) as exc:
                record["execution_errors"].append(
                    f"Could not revalidate evaluation or target identity after execution: {exc}"
                )
            record.update(self._summarize(project, record))
            record["finished_at"] = timestamp()
            self._redact_diagnostics(project, record)
            destination = safe_path(
                project.root,
                str((project.state / "runs" / f"{record['id']}.json").relative_to(project.root)),
                must_exist=False,
            )
            write_record(destination, record)
            return record

    @staticmethod
    def _redact_diagnostics(project: Project, record: dict) -> None:
        env_names = set(project.contract.evaluator_env)
        for config in project.contract.targets.values():
            env_names.update(config.env)
        secrets = [os.environ[name] for name in env_names if name in os.environ]
        # Redact native diagnostics, not structural IDs/policy/hashes: an ordinary environment
        # setting such as APP_MODE=candidate must not corrupt target identity or verification.
        for observation in record.get("observations", []):
            for field in (
                "actual_output",
                "metadata",
                "reason",
                "error",
                "context",
                "retrieval_context",
                "tools_called",
            ):
                if field in observation:
                    observation[field] = redact(observation[field], secrets)
        for key in (
            "execution_errors",
            "gaps",
            "control_gaps",
            "application_gaps",
            "inspection_gaps",
        ):
            if key in record:
                record[key] = redact(record[key], secrets)
        for key, settings in record.get("metrics", {}).items():
            record["metrics"][key] = redact(settings, secrets)
        for control in record.get("controls", []):
            for field in ("source", "reviewed_by", "evidence"):
                if field in control:
                    control[field] = redact(control[field], secrets)

    @staticmethod
    def _source_identity(project: Project, bundle: dict, target: dict | None) -> dict:
        declared_files = dict(bundle["criteria"]["files"])
        declared_files.update((target or {}).get("files", {}))
        result: dict[str, Any] = {
            "scope": "Declared evaluation and target files only; not the entire repository",
            "declared_files": declared_files,
            "declared_files_digest": digest(declared_files),
            "git_revision": None,
            "git_status": None,
        }
        try:
            revision = subprocess.run(
                ["git", "-C", str(project.root), "rev-parse", "--verify", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if revision.returncode == 0:
                result["git_revision"] = revision.stdout.strip()
            if declared_files:
                status = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(project.root),
                        "status",
                        "--porcelain=v1",
                        "--untracked-files=normal",
                        "--",
                        *sorted(declared_files),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if status.returncode == 0:
                    result["git_status"] = status.stdout.splitlines()
        except (OSError, subprocess.TimeoutExpired):
            result["git_status"] = None
        return result

    def _runs(self, project: Project) -> list[dict]:
        directory = safe_path(
            project.root, str((project.state / "runs").relative_to(project.root)), must_exist=False
        )
        if not directory.exists():
            return []
        records = []
        for path in sorted(directory.glob("*.json")):
            record = read_record(path)
            self._validate_run(record, path)
            if record["kind"] == "baseline-unavailable":
                record["decision"] = "UNAVAILABLE"
            else:
                record.update(self._summarize(project, record))
            records.append(record)
        return records

    def _summarize(self, project: Project, record: dict) -> dict:
        observations = record["observations"]
        if record["kind"] == "audit" and isinstance(observations, list):
            observations = [
                {**row, "passed": row["observed_passed"] is row["expected_pass"]}
                if isinstance(row, dict)
                and not row.get("error")
                and type(row.get("observed_passed")) is bool
                and type(row.get("expected_pass")) is bool
                else row
                for row in observations
            ]
        saved_requirements = (
            record.get("bundle_identity", {})
            .get("criteria", {})
            .get("contract", {})
            .get("requirements")
        )
        requirements = project.contract.requirements
        if isinstance(saved_requirements, list):
            try:
                from .models import Requirement

                requirements = [Requirement.model_validate(item) for item in saved_requirements]
            except ValueError:
                requirements = project.contract.requirements
        summary = decide(
            requirements,
            record["expected_ids"],
            observations,
            audit=record["kind"] == "audit",
            gaps=record.get("inspection_gaps", record["gaps"]),
            allow_empty=bool(
                record["kind"] != "audit"
                and isinstance(record.get("cases"), list)
                and not any(
                    record["profile"] in case.get("profiles", [])
                    and not case.get("deferred_reason")
                    for case in record["cases"]
                    if isinstance(case, dict)
                )
            ),
        )
        summary["integrity_errors"].extend(self._plan_errors(record))
        if summary["integrity_errors"] or (
            record["execution_errors"] and summary["decision"] != "FAIL"
        ):
            summary["decision"] = "ERROR"
        return summary

    @staticmethod
    def _plan_errors(record: dict) -> list[str]:
        errors = []
        rows = record.get("expected_rows")
        if not isinstance(rows, list):
            return ["Missing or invalid execution observation plan"]
        expected = {}
        fields: tuple[str, ...] = ("id", "case_id", "requirement_id", "trial", "repetition")
        if record["kind"] == "audit":
            fields += ("control_id", "expected_pass")
        for row in rows:
            if (
                not isinstance(row, dict)
                or any(key not in row for key in fields)
                or any(
                    not isinstance(row[key], str) or not row[key].strip()
                    for key in ("id", "case_id", "requirement_id")
                )
                or any(type(row[key]) is not int or row[key] < 1 for key in ("trial", "repetition"))
            ):
                errors.append("Invalid planned observation metadata")
                continue
            if row["id"] in expected:
                errors.append("Duplicate planned observation identity")
            expected[row["id"]] = row
            if row["repetition"] > record["execution_policy"]["grader_repetitions"]:
                errors.append("Planned grader repetition exceeds execution policy")
            if row["trial"] > (
                1 if record["kind"] == "audit" else record["execution_policy"]["trials"]
            ):
                errors.append("Planned trial exceeds execution policy")
            if record["kind"] == "audit" and (
                not isinstance(row["control_id"], str)
                or not row["control_id"].strip()
                or type(row["expected_pass"]) is not bool
            ):
                errors.append("Invalid planned control metadata")
        if list(expected) != record["expected_ids"]:
            errors.append("Expected observation identities do not match the execution plan")
        for row in record["observations"] if isinstance(record["observations"], list) else []:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                continue  # The decision policy separately rejects malformed observations.
            plan = expected.get(row["id"])
            if plan is None or any(row.get(key) != plan[key] for key in fields):
                errors.append(
                    "Observed case, requirement, or execution coordinates do not match plan"
                )
            if (not row.get("error") and not isinstance(row.get("metadata"), dict)) or (
                row.get("error")
                and row.get("metadata") is not None
                and not isinstance(row["metadata"], dict)
            ):
                errors.append("Observed native metadata must be an object")
            if (
                record["kind"] == "audit"
                and not row.get("error")
                and (
                    type(row.get("observed_passed")) is not bool
                    or type(row.get("expected_pass")) is not bool
                )
            ):
                errors.append("Control audit requires observed and expected boolean outcomes")
        return errors

    def _validate_run(self, record: dict, path: Path) -> None:
        required = {
            "schema_version",
            "id",
            "created_at",
            "finished_at",
            "kind",
            "change",
            "profile",
            "bundle_identity",
            "bundle_digest",
            "criteria_digest",
        }
        try:
            if (
                not required.issubset(record)
                or type(record["schema_version"]) is not int
                or record["schema_version"] != 1
                or record["change"] != self.change
                or record["id"] != path.stem
                or not isinstance(record["id"], str)
                or not record["id"].strip()
                or record["kind"] not in {"audit", "baseline", "candidate", "baseline-unavailable"}
                or record["profile"] not in {"dev", "acceptance"}
            ):
                raise ValueError("invalid header")
            for key in ("created_at", "finished_at"):
                if datetime.fromisoformat(record[key]).utcoffset() is None:
                    raise ValueError("timestamps must have a timezone")
            identity = record["bundle_identity"]
            if (
                not isinstance(identity, dict)
                or set(identity) != {"criteria", "runtime", "evaluator_env"}
                or not isinstance(identity["criteria"], dict)
                or set(identity["criteria"]) != {"contract", "files"}
                or not isinstance(identity["runtime"], dict)
                or not identity["runtime"]
                or not isinstance(identity["evaluator_env"], dict)
                or digest(identity) != record["bundle_digest"]
                or digest(identity["criteria"]) != record["criteria_digest"]
            ):
                raise ValueError("invalid bundle identity")
            if record["kind"] == "baseline-unavailable":
                if (
                    not isinstance(record.get("reason"), str)
                    or not record["reason"].strip()
                    or record["profile"] != "acceptance"
                    or "observations" in record
                ):
                    raise ValueError("invalid unavailable baseline declaration")
                return
            for key in ("execution_errors", "gaps"):
                if not isinstance(record[key], list) or any(
                    not isinstance(value, str) or not value.strip() for value in record[key]
                ):
                    raise ValueError("invalid execution metadata")
            if not {"observations", "expected_ids"}.issubset(record):
                raise ValueError("missing execution observations")
            policy = record["execution_policy"]
            if (
                not isinstance(policy, dict)
                or set(policy) != set(Profile.model_fields)
                or policy != identity["criteria"]["contract"]["profiles"][record["profile"]]
            ):
                raise ValueError("invalid execution policy")
            Profile.model_validate(policy)
            if record["kind"] != "audit":
                if (
                    not isinstance(record.get("target"), str)
                    or not record["target"].strip()
                    or not isinstance(record.get("target_identity"), dict)
                    or record.get("target_digest") != digest(record["target_identity"])
                    or record.get("target_kind") != record["target_identity"]["config"]["kind"]
                ):
                    raise ValueError("invalid target identity")
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectError(f"Invalid run metadata or identity: {path.name}: {exc}") from exc

    def _latest(
        self, runs: list[dict], kind: str | tuple[str, ...], profile: str = "acceptance"
    ) -> dict | None:
        kinds = (kind,) if isinstance(kind, str) else kind
        return next(
            (run for run in reversed(runs) if run["kind"] in kinds and run["profile"] == profile),
            None,
        )

    def run_record(self, run_id: str) -> dict:
        """Load one validated saved run without changing project state."""
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
            raise ProjectError("Invalid run ID")
        project = self.project
        path = safe_path(
            project.root,
            str((project.state / "runs" / f"{run_id}.json").relative_to(project.root)),
        )
        if not path.is_file():
            raise ProjectError(f"Unknown run: {run_id}")
        record = read_record(path)
        self._validate_run(record, path)
        if record["kind"] == "baseline-unavailable":
            record["decision"] = "UNAVAILABLE"
        else:
            record.update(self._summarize(project, record))
        return record

    @staticmethod
    def _case_changes(before: dict, after: dict) -> dict:
        def indexed(run: dict) -> dict[str, dict]:
            return {
                row["case_id"]: row
                for row in run.get("cases", [])
                if isinstance(row, dict) and isinstance(row.get("case_id"), str)
            }

        old, new = indexed(before), indexed(after)
        shared = old.keys() & new.keys()
        return {
            "added": sorted(new.keys() - old.keys()),
            "removed": sorted(old.keys() - new.keys()),
            "changed": sorted(key for key in shared if old[key] != new[key]),
        }

    def compare_runs(self, before_id: str, after_id: str) -> dict:
        before, after = self.run_record(before_id), self.run_record(after_id)
        allowed_kinds = {"baseline", "candidate", "baseline-unavailable"}
        if before["kind"] not in allowed_kinds or after["kind"] not in allowed_kinds:
            raise ProjectError("Only application measurements can be compared")
        changes = self._case_changes(before, after)
        comparison: dict[str, Any]
        if (
            before.get("kind") == "baseline-unavailable"
            or after.get("kind") == "baseline-unavailable"
        ):
            comparison = {
                "status": "unavailable",
                "reason": "An unavailable-baseline declaration has no observations to compare",
            }
        elif before["profile"] != after["profile"]:
            comparison = {"status": "unavailable", "reason": "Execution profiles differ"}
        elif before["bundle_digest"] != after["bundle_digest"]:
            comparison = {
                "status": "unavailable",
                "reason": "Evaluation bundles differ; rerun both targets with the current bundle",
            }
        else:
            comparison = self._compare(before, after)
        comparison.update(
            {
                "schema_version": 1,
                "kind": "measurement-comparison",
                "change": self.change,
                "before_run_id": before_id,
                "after_run_id": after_id,
                "case_changes": changes,
            }
        )
        if comparison["status"] == "comparable":
            old_rows = {row["id"]: row for row in before["observations"]}
            new_rows = {row["id"]: row for row in after["observations"]}
            comparison["changed_observations"] = [
                {
                    "id": identity,
                    "case_id": new_rows[identity]["case_id"],
                    "requirement_id": new_rows[identity]["requirement_id"],
                    "before_passed": old_rows[identity].get("passed"),
                    "after_passed": new_rows[identity].get("passed"),
                    "before_score": old_rows[identity].get("score"),
                    "after_score": new_rows[identity].get("score"),
                }
                for identity in before["expected_ids"]
                if old_rows.get(identity, {}).get("passed")
                != new_rows.get(identity, {}).get("passed")
                or old_rows.get(identity, {}).get("score")
                != new_rows.get(identity, {}).get("score")
            ]
        return comparison

    def measurement_report(
        self,
        run: dict,
        *,
        comparison: dict | None = None,
        application_revision: str | None = None,
    ) -> dict:
        from .reporting import build_measurement_report

        return build_measurement_report(
            self.project,
            run=run,
            comparison=comparison,
            application_revision=application_revision,
        )

    def measure(
        self,
        target: str,
        *,
        stage: Literal["baseline", "candidate"] = "candidate",
        profile: str = "dev",
        allow_paid: bool = False,
        compare_to: str | None = None,
        report_dir: str | None = None,
        application_revision: str | None = None,
    ) -> dict:
        run = self.run(target, stage=stage, profile=profile, allow_paid=allow_paid)
        comparison = self.compare_runs(compare_to, run["id"]) if compare_to else None
        report = self.measurement_report(
            run, comparison=comparison, application_revision=application_revision
        )
        directory = report_dir or str(
            (self.project.state / "measurements" / run["id"]).relative_to(self.project.root)
        )
        paths = self.write_measurement_report(directory, report)
        return {**report, "report_paths": paths}

    def write_measurement_report(self, directory: str, report: dict) -> dict[str, str]:
        from .reporting import write_report_bundle

        return write_report_bundle(self.project, directory, report)

    def measurement_status(self) -> dict:
        project = self.project
        inspection = self.inspect(profile="dev")
        runs = [
            run
            for run in self._runs(project)
            if run["kind"] in {"baseline", "candidate"} and run["profile"] == "dev"
        ]
        latest = runs[-1] if runs else None
        current = bool(
            latest
            and latest["bundle_digest"] == project.bundle_digest()
            and self._target_current(project, latest)
        )
        execution_status = self._measurement_execution_status(latest) if latest else None
        runnable_cases = [row for row in inspection["cases"] if not row.get("deferred_reason")]
        if inspection["execution_errors"] or not runnable_cases:
            phase, state = "prepare", "needs-attention"
            summary = "The measurement pipeline needs a runnable scenario"
            action = {
                "id": "prepare-measurement",
                "actor": "agent",
                "label": "Prepare the first runnable measurement",
                "chat": f"$edd-prepare {self.change}",
            }
        elif not current:
            phase, state = "measure", "ready"
            summary = "The scenario set is ready for a fresh measurement"
            action = {
                "id": "run-measurement",
                "actor": "cli",
                "label": "Run the current application",
                "command": f"edd measure {self.change} --target TARGET",
            }
        elif execution_status in {"ERROR", "INCONCLUSIVE"}:
            phase, state = "measure", "needs-attention"
            summary = f"The latest measurement is {execution_status.lower()}"
            action = {
                "id": "repair-measurement",
                "actor": "agent",
                "label": "Inspect and resolve incomplete measurement evidence",
                "chat": f"$edd-check {self.change}",
            }
        elif latest and latest["kind"] == "baseline":
            phase, state = "improve", "measured"
            summary = "The starting behavior is measured and ready to improve"
            action = {
                "id": "build-candidate",
                "actor": "agent",
                "label": "Implement the next behavior slice and measure the candidate",
                "chat": f"$edd-build {self.change}",
            }
        elif latest and latest["decision"] == "PASS":
            phase, state = "measure", "measured"
            summary = "The latest measurement completed with all declared checks passing"
            action = {
                "id": "inspect-or-extend",
                "actor": "agent",
                "label": "Inspect results or extend scenarios when new evidence appears",
                "chat": f"$edd-check {self.change}",
            }
        else:
            phase, state = "improve", "measured"
            summary = "The latest measurement found behavior to improve"
            action = {
                "id": "improve-candidate",
                "actor": "agent",
                "label": "Improve the application from the measured failures",
                "chat": f"$edd-build {self.change}",
            }
        return {
            "schema_version": 2,
            "mode": "measurement",
            "change": self.change,
            "criteria_digest": project.criteria_digest(),
            "scenario_count": len(inspection["cases"]),
            "deferred_count": sum(bool(row.get("deferred_reason")) for row in inspection["cases"]),
            "latest_measurement": (
                {
                    **self._run_status(latest, project.bundle_digest(), current=current),
                    "execution_status": execution_status,
                    "behavior_decision": latest["decision"],
                }
                if latest
                else {"status": "missing"}
            ),
            "workflow": {"phase": phase, "state": state, "summary": summary},
            "actions": [action],
            "acceptance": {
                "optional": True,
                "command": f"edd status {self.change} --acceptance",
            },
        }

    @staticmethod
    def _measurement_execution_status(run: dict) -> str:
        if run.get("execution_errors") or run.get("integrity_errors") or run.get("errors"):
            return "ERROR"
        if run.get("missing") or run.get("gaps"):
            return "INCONCLUSIVE"
        return "COMPLETE"

    def _review(self, project: Project) -> dict:
        return review_state(project, load_review(project))

    def verify(self) -> dict:
        project = self.project
        runs = self._runs(project)
        bundle = project.bundle_digest()
        review = self._review(project)
        packet_state = stored_packet_status(project, load_review(project))
        audit = self._latest(runs, "audit")
        candidate = self._latest(runs, "candidate")
        baseline = self._latest(runs, ("baseline", "baseline-unavailable"))
        gaps = []
        if review["status"] != "current":
            gaps.append(f"Criteria review is {review['status']}")
        if packet_state != "current":
            gaps.append(f"Committed review packet is {packet_state}")
        for name, run in (("Control audit", audit), ("Candidate acceptance", candidate)):
            if run is None:
                gaps.append(f"{name} has not run with the acceptance profile")
            elif run["bundle_digest"] != bundle:
                gaps.append(f"{name} is stale for the current evaluation bundle")
        candidate_current = bool(candidate and candidate["bundle_digest"] == bundle)
        if candidate_current and candidate is not None:
            if candidate.get("target_kind") != "application":
                gaps.append(
                    "Acceptance requires an application target, not stub/reference evidence"
                )
                candidate_current = False
            if candidate.get("target") not in project.contract.targets:
                gaps.append("Candidate target is no longer configured")
                candidate_current = False
            elif not self._target_current(project, candidate):
                gaps.append("Candidate evidence is stale for current target code or configuration")
                candidate_current = False
        applicable = [run for run in (audit,) if run and run["bundle_digest"] == bundle]
        if candidate_current and candidate is not None:
            applicable.append(candidate)
        if any(run["decision"] == "FAIL" for run in applicable):
            decision = "FAIL"
        elif any(run["decision"] == "ERROR" for run in applicable):
            decision = "ERROR"
        elif gaps or len(applicable) != 2 or any(run["decision"] != "PASS" for run in applicable):
            decision = "INCONCLUSIVE"
        else:
            decision = "PASS"
        comparison = {"status": "unavailable", "reason": "No matching baseline and candidate"}
        if (
            baseline
            and candidate is not None
            and candidate_current
            and baseline["bundle_digest"] == bundle
        ):
            comparison = self._compare(baseline, candidate)
        next_steps = list(gaps)
        if audit and audit["decision"] != "PASS":
            next_steps.append(
                "Inspect the control audit, correct criteria or evidence, then rerun edd audit"
            )
        if candidate and candidate["decision"] != "PASS":
            next_steps.append(
                "Inspect candidate failures and rerun after implementing the remaining behavior"
            )
        return {
            "schema_version": 1,
            "change": self.change,
            "decision": decision,
            "review": review,
            "review_packet": {"status": packet_state},
            "audit": self._run_status(audit, bundle),
            "candidate": self._run_status(candidate, bundle, current=candidate_current),
            "baseline": self._run_status(baseline, bundle),
            "comparison": comparison,
            "gaps": gaps,
            "next_steps": next_steps,
            "evidence_scope": (
                "Reviewed cooperative code; local checksums are not authenticated approval"
            ),
        }

    def acceptance_report(
        self,
        *,
        fresh_run_ids: set[str] | None = None,
        application_revision: str | None = None,
    ) -> dict:
        from .reporting import build_report

        project = self.project
        runs = self._runs(project)
        audit = self._latest(runs, "audit")
        candidate = self._latest(runs, "candidate")
        return build_report(
            project,
            packet=self.review_packet(),
            verification=self.verify(),
            audit=audit,
            candidate=candidate,
            fresh_run_ids=set(fresh_run_ids or set()),
            application_revision=application_revision,
        )

    def write_acceptance_report(self, directory: str, report: dict) -> dict[str, str]:
        from .reporting import write_report_bundle

        return write_report_bundle(self.project, directory, report)

    def check(
        self,
        target: str,
        *,
        allow_paid: bool = False,
        report_dir: str | None = None,
        application_revision: str | None = None,
    ) -> dict:
        audit = self.audit(allow_paid=allow_paid)
        candidate = self.run(target, stage="candidate", profile="acceptance", allow_paid=allow_paid)
        verification = self.verify()
        fresh = {audit["id"], candidate["id"]}
        report = self.acceptance_report(
            fresh_run_ids=fresh, application_revision=application_revision
        )
        paths = self.write_acceptance_report(report_dir, report) if report_dir else None
        return {
            **verification,
            "fresh_run_ids": sorted(fresh),
            "report": report,
            "report_paths": paths,
        }

    @staticmethod
    def _target_current(project: Project, run: dict) -> bool:
        try:
            return run.get("target_digest") == project.target_digest(run["target"])
        except ProjectError:
            return False

    def _run_status(self, run: dict | None, bundle: str, *, current: bool | None = None) -> dict:
        if run is None:
            return {"status": "missing"}
        if current is None:
            current = run["bundle_digest"] == bundle
        if run["kind"] == "baseline-unavailable":
            return {
                "status": "current" if current else "stale",
                "id": run["id"],
                "decision": "UNAVAILABLE",
                "profile": run["profile"],
                "reason": run["reason"],
            }
        return {
            "status": "current" if current else "stale",
            "id": run["id"],
            "decision": run["decision"],
            "profile": run["profile"],
            "target": run.get("target"),
            "target_kind": run.get("target_kind"),
            "requirements": run["requirements"],
            "gaps": run["gaps"],
            "execution_errors": run["execution_errors"],
        }

    def _compare(self, baseline: dict, candidate: dict) -> dict:
        if baseline["kind"] == "baseline-unavailable":
            return {"status": "unavailable", "reason": baseline["reason"]}
        if baseline["expected_ids"] != candidate["expected_ids"]:
            return {"status": "unavailable", "reason": "Observation plans differ"}
        if any(
            run["errors"]
            or run["missing"]
            or run["execution_errors"]
            or run["integrity_errors"]
            or run["decision"] not in {"PASS", "FAIL"}
            for run in (baseline, candidate)
        ):
            return {
                "status": "unavailable",
                "reason": "One run has incomplete or errored observations",
            }
        deltas = {}
        for req, current in candidate["requirements"].items():
            old = baseline["requirements"].get(req, {}).get("pass_rate")
            new = current.get("pass_rate")
            if old is not None and new is not None:
                deltas[req] = new - old
        return {
            "status": "comparable",
            "baseline_kind": baseline.get("target_kind"),
            "deltas": deltas,
            "improved_requirements": [req for req, delta in deltas.items() if delta > 0],
            "regressed_requirements": [req for req, delta in deltas.items() if delta < 0],
            "note": "Observed sample differences; repeated trials are not independent scenarios",
        }

    def status(self) -> dict:
        result = self.verify()
        ready = (
            result["review_packet"]["status"] == "current"
            and result["review"]["status"] == "current"
            and result["audit"].get("status") == "current"
            and result["audit"].get("decision") == "PASS"
            and result["baseline"].get("status") == "current"
            and result["baseline"].get("decision") in {"PASS", "FAIL", "UNAVAILABLE"}
        )
        if not ready:
            next_steps = []
            if result["review_packet"]["status"] != "current":
                next_steps.append(
                    f"Generate and commit the current packet with edd review {self.change} --write"
                )
            if result["review"].get("domain", {}).get("status") != "approved":
                next_steps.append(
                    f"Review the domain expectations in evals/{self.change}/REVIEW.md and record "
                    "an explicit domain decision"
                )
            if result["audit"].get("status") != "current":
                next_steps.append(f"Run edd audit {self.change} against the current criteria")
            elif result["audit"].get("decision") != "PASS":
                next_steps.append(
                    "Resolve control-label or grader/evidence defects; inspect "
                    f"edd report {self.change} --run {result['audit']['id']}, then rerun edd audit"
                )
            if (
                result["review"].get("technical", {}).get("status") != "approved"
                and result["audit"].get("status") == "current"
                and result["audit"].get("decision") == "PASS"
            ):
                next_steps.append(
                    "Review the technical validation and record an explicit technical decision"
                )
            if result["baseline"].get("status") != "current" or result["baseline"].get(
                "decision"
            ) not in {"PASS", "FAIL", "UNAVAILABLE"}:
                next_steps.append(
                    "Run an acceptance-profile baseline, or record its genuine unavailability "
                    f"with edd baseline-unavailable {self.change} --reason TEXT"
                )
            result["next_steps"] = next_steps
        status = {
            **result,
            "ready_to_build": ready,
            "accepted": result["decision"] == "PASS",
        }
        workflow, diagnostics, actions = self._workflow_view(status)
        return {**status, "workflow": workflow, "diagnostics": diagnostics, "actions": actions}

    def _workflow_view(self, status: dict) -> tuple[dict, list[dict], list[dict]]:
        review = status["review"]
        audit = status["audit"]
        baseline = status["baseline"]
        candidate = status["candidate"]
        accepted = status["accepted"]
        ready = status["ready_to_build"]

        checklist = [
            {"id": "draft", "label": "Evaluation draft", "status": "complete"},
            {
                "id": "packet",
                "label": "Specialist packet",
                "status": (
                    "complete"
                    if status["review_packet"].get("status") == "current"
                    else status["review_packet"].get("status", "missing")
                ),
            },
            {
                "id": "domain-review",
                "label": "Domain approval",
                "status": (
                    "complete"
                    if review.get("domain", {}).get("status") == "approved"
                    else review.get("domain", {}).get("status", "missing")
                ),
            },
            {
                "id": "audit",
                "label": "Grader audit",
                "status": self._check_status(audit, accepted_decisions={"PASS"}),
            },
            {
                "id": "technical-review",
                "label": "Technical validation",
                "status": (
                    "complete"
                    if review.get("technical", {}).get("status") == "approved"
                    else review.get("technical", {}).get("status", "missing")
                ),
            },
            {
                "id": "baseline",
                "label": "Baseline",
                "status": self._check_status(
                    baseline, accepted_decisions={"PASS", "FAIL", "UNAVAILABLE"}
                ),
            },
            {
                "id": "candidate",
                "label": "Candidate acceptance",
                "status": self._check_status(candidate, accepted_decisions={"PASS"}),
            },
        ]
        if accepted:
            phase, state, summary = "complete", "accepted", "Current candidate is accepted"
        elif not ready:
            remaining = sum(item["status"] != "complete" for item in checklist[1:6])
            phase, state = "prepare", "in-progress"
            summary = f"{remaining} preparation step{'s' if remaining != 1 else ''} remain"
        elif candidate.get("decision") == "FAIL":
            phase, state, summary = "build", "needs-changes", "Candidate behavior needs changes"
        elif candidate.get("status") == "current" and candidate.get("decision") in {
            "ERROR",
            "INCONCLUSIVE",
        }:
            phase, state = "check", "needs-attention"
            summary = "Acceptance evidence needs attention"
        else:
            phase, state, summary = "build", "ready", "Criteria are ready for implementation"

        diagnostics = self._diagnostics(status)
        actions = self._actions(status)
        return (
            {"phase": phase, "state": state, "summary": summary, "checklist": checklist},
            diagnostics,
            actions,
        )

    @staticmethod
    def _check_status(record: dict, *, accepted_decisions: set[str]) -> str:
        if record.get("status") != "current":
            return record.get("status", "missing")
        return "complete" if record.get("decision") in accepted_decisions else "attention"

    @staticmethod
    def _diagnostics(status: dict) -> list[dict]:
        diagnostics = []
        packet_state = status["review_packet"].get("status", "missing")
        if packet_state != "current":
            diagnostics.append(
                {
                    "code": f"review-packet-{packet_state}",
                    "severity": "blocking",
                    "artifact": "review-packet",
                    "message": f"Committed review packet is {packet_state}",
                    "repair_phase": "prepare",
                }
            )
        for area in ("domain", "technical"):
            state = status["review"].get(area, {}).get("status", "missing")
            if state != "approved":
                diagnostics.append(
                    {
                        "code": f"{area}-review-{state}",
                        "severity": "blocking",
                        "artifact": f"{area}-review",
                        "message": f"{area.title()} review is {state}",
                        "repair_phase": "prepare",
                    }
                )
        mappings = (
            ("audit", status["audit"], "grader-audit", {"PASS"}),
            ("baseline", status["baseline"], "baseline", {"PASS", "FAIL", "UNAVAILABLE"}),
            ("candidate", status["candidate"], "candidate-acceptance", {"PASS"}),
        )
        for artifact, record, code, accepted in mappings:
            if artifact == "candidate" and not status["ready_to_build"]:
                continue
            state = record.get("status", "missing")
            decision = record.get("decision")
            if state != "current":
                diagnostics.append(
                    {
                        "code": f"{code}-{state}",
                        "severity": "blocking",
                        "artifact": artifact,
                        "message": f"{artifact.replace('-', ' ').title()} is {state}",
                        "repair_phase": "prepare" if artifact != "candidate" else "check",
                    }
                )
            elif decision not in accepted:
                diagnostics.append(
                    {
                        "code": f"{code}-{decision.lower()}",
                        "severity": "blocking" if decision in {"FAIL", "ERROR"} else "warning",
                        "artifact": artifact,
                        "message": f"{artifact.replace('-', ' ').title()} is {decision}",
                        "repair_phase": "build" if artifact == "candidate" else "prepare",
                    }
                )
        return diagnostics

    def _actions(self, status: dict) -> list[dict]:
        actions = []
        build_chat = self._chat_invocation("edd-build")
        check_chat = self._chat_invocation("edd-check")

        def add(action_id, actor, label, command=None, chat=None):
            actions.append(
                {
                    "id": action_id,
                    "actor": actor,
                    "label": label,
                    "command": command,
                    "chat": chat,
                    "blocking": True,
                }
            )

        digest_value = self.project.criteria_digest()
        if status["review_packet"].get("status") != "current":
            add(
                "write-review-packet",
                "cli",
                "Generate and commit the current specialist review packet",
                f"edd review {self.change} --write",
            )
        if status["review"].get("domain", {}).get("status") != "approved":
            add(
                "review-criteria",
                "reviewer",
                "Review and decide the domain expectations",
                f'edd review {self.change} --area domain --decision approve --by "NAME" '
                f'--note "RATIONALE" --criteria-digest {digest_value}',
            )
        if status["audit"].get("status") != "current" or status["audit"].get("decision") != "PASS":
            add(
                "audit-graders",
                "cli",
                "Run the grader audit and resolve any mismatches",
                f"edd audit {self.change}",
            )
        if (
            status["review"].get("technical", {}).get("status") != "approved"
            and status["audit"].get("status") == "current"
            and status["audit"].get("decision") == "PASS"
        ):
            add(
                "review-graders",
                "reviewer",
                "Review and decide the technical validation",
                f'edd review {self.change} --area technical --decision approve --by "NAME" '
                f'--note "RATIONALE" --criteria-digest {digest_value}',
            )
        if status["baseline"].get("status") != "current" or status["baseline"].get(
            "decision"
        ) not in {"PASS", "FAIL", "UNAVAILABLE"}:
            project = self.project
            baseline_targets = [
                name
                for name, target in project.contract.targets.items()
                if target.kind in {"stub", "reference"}
            ]
            command = (
                f"edd run {self.change} --target {baseline_targets[0]} --stage baseline"
                if len(baseline_targets) == 1
                else f"edd inspect {self.change}"
            )
            add("record-baseline", "cli", "Run or explicitly waive the baseline", command)
        if status["ready_to_build"] and not status["accepted"]:
            candidate = status["candidate"]
            if candidate.get("decision") == "FAIL":
                run_id = candidate.get("id")
                add(
                    "fix-candidate",
                    "agent" if build_chat else "developer",
                    "Inspect the failed evidence and implement the remaining behavior",
                    f"edd report {self.change} --run {run_id}" if run_id else None,
                    f"{build_chat} {self.change}" if build_chat else None,
                )
            elif candidate.get("decision") in {"ERROR", "INCONCLUSIVE"}:
                add(
                    "repair-check",
                    "agent" if check_chat else "developer",
                    "Resolve incomplete or errored acceptance evidence",
                    f"edd report {self.change} --run {candidate.get('id')}",
                    f"{check_chat} {self.change}" if check_chat else None,
                )
            else:
                application_targets = [
                    name
                    for name, target in self.project.contract.targets.items()
                    if target.kind == "application"
                ]
                target = (
                    "candidate"
                    if "candidate" in application_targets
                    else application_targets[0]
                    if len(application_targets) == 1
                    else None
                )
                add(
                    "build-change",
                    "agent" if build_chat else "developer",
                    (
                        "Implement the reviewed behavior with the coding-agent workflow"
                        if build_chat
                        else "Implement the reviewed behavior; run acceptance when ready"
                    ),
                    f"edd check {self.change} --target {target}"
                    if target
                    else f"edd inspect {self.change}",
                    f"{build_chat} {self.change}" if build_chat else None,
                )
        return actions

    def _chat_invocation(self, skill: str) -> str | None:
        if (self.root / ".claude" / "skills" / skill).is_dir():
            return f"/{skill}"
        if (self.root / ".agents" / "skills" / skill).is_dir():
            return f"${skill}"
        return None
