"""Fail-closed policy over observations; no model or application execution here."""

from collections import Counter

from .models import Requirement


def decide(
    requirements: list[Requirement],
    expected: list[str],
    observations: list[dict],
    *,
    audit: bool = False,
    gaps: list[str] | None = None,
    allow_empty: bool = False,
) -> dict:
    integrity_errors = []
    if not isinstance(gaps, (list, type(None))) or any(
        not isinstance(gap, str) or not gap.strip() for gap in (gaps or [])
    ):
        integrity_errors.append("Coverage gaps must be nonempty text")
        gaps = []
    gaps = list(gaps or [])
    if not isinstance(expected, list):
        integrity_errors.append("Expected observation identities must be a list")
        expected = []
    expected_ids = {identity for identity in expected if isinstance(identity, str) and identity}
    if (not expected and not allow_empty) or len(expected) != len(expected_ids):
        integrity_errors.append("Expected observation identities must be nonempty and unique")
    if not isinstance(observations, list):
        integrity_errors.append("Observations must be a list")
        observations = []
    completed = len(observations)
    if any(not isinstance(row, dict) for row in observations):
        integrity_errors.append("Observation metadata must be an object")
    observations = [row for row in observations if isinstance(row, dict)]
    ids = [row["id"] for row in observations if isinstance(row.get("id"), str) and row["id"]]
    if len(ids) != len(observations):
        integrity_errors.append("Observation identity must be nonempty text")
    if len(ids) != len(set(ids)) or any(identity not in expected_ids for identity in ids):
        integrity_errors.append("Duplicate or unexpected observation identities")
    req_ids = {req.id for req in requirements}
    for row in observations:
        if not isinstance(row.get("requirement_id"), str) or row["requirement_id"] not in req_ids:
            integrity_errors.append("Unknown observation requirement")
        if not isinstance(row.get("case_id"), str) or not row["case_id"].strip():
            integrity_errors.append("Observation case identity must be nonempty text")
        if row.get("error") is not None and (
            not isinstance(row["error"], str) or not row["error"].strip()
        ):
            integrity_errors.append("Observation error must be null or nonempty text")
        if not row.get("error") and type(row.get("passed")) is not bool:
            integrity_errors.append("Completed observation must have a boolean result")
    errors = sum(bool(row.get("error")) for row in observations)
    missing = len(expected_ids - set(ids))
    summaries = {}
    decisive_failure = False
    for req in requirements:
        rows = [row for row in observations if row.get("requirement_id") == req.id]
        complete = [
            row
            for row in rows
            if not row.get("error")
            and type(row.get("passed")) is bool
            and isinstance(row.get("case_id"), str)
            and row["case_id"].strip()
        ]
        passed = sum(row["passed"] for row in complete)
        failed = len(complete) - passed
        unique_cases = len({row["case_id"] for row in complete})
        # Missing observations could still pass. Without per-requirement expected identities,
        # use the total missing count as a conservative upper bound before declaring failure.
        best_denominator = len(rows) + missing
        best_rate = (best_denominator - failed) / best_denominator if best_denominator else 0
        if (audit or req.critical) and failed:
            decisive_failure = True
        elif failed and best_rate < req.pass_rate:
            decisive_failure = True
        if not audit and unique_cases < req.min_cases:
            gaps.append(
                f"{req.id}: requires {req.min_cases} unique cases; completed {unique_cases}"
            )
        summaries[req.id] = {
            "passed": passed,
            "failed": failed,
            "errors": len(rows) - len(complete),
            "unique_cases": unique_cases,
            "pass_rate": passed / len(complete) if complete else None,
            "required_pass_rate": 1.0 if audit or req.critical else req.pass_rate,
            "critical": req.critical,
        }
    if integrity_errors:
        decision = "ERROR"
    elif decisive_failure:
        decision = "FAIL"
    elif errors:
        decision = "ERROR"
    elif missing or gaps:
        decision = "INCONCLUSIVE"
    else:
        decision = "PASS"
    return {
        "decision": decision,
        "expected": len(expected),
        "completed": completed,
        "errors": errors,
        "missing": missing,
        "requirements": summaries,
        "gaps": gaps,
        "integrity_errors": integrity_errors,
        "counts": dict(
            Counter(
                "error" if row.get("error") else "pass" if row.get("passed") else "fail"
                for row in observations
            )
        ),
    }
