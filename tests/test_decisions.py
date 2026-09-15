from edd_kit.decisions import decide
from edd_kit.models import Requirement


def test_critical_violation_remains_failure_when_another_observation_errors():
    requirements = [Requirement(id="safety", description="Safe", critical=True)]
    expected = ["one", "two"]
    observations = [
        {"id": "one", "requirement_id": "safety", "case_id": "one", "passed": False, "error": None},
        {
            "id": "two",
            "requirement_id": "safety",
            "case_id": "two",
            "passed": None,
            "error": "timeout",
        },
    ]
    result = decide(requirements, expected, observations)
    assert result["decision"] == "FAIL"
    assert result["errors"] == 1


def test_missing_or_duplicate_observations_never_pass():
    requirements = [Requirement(id="correct", description="Correct")]
    observation = {
        "id": "one",
        "requirement_id": "correct",
        "case_id": "one",
        "passed": True,
        "error": None,
    }
    assert decide(requirements, ["one", "two"], [observation])["decision"] == "INCONCLUSIVE"
    assert decide(requirements, ["one"], [observation, observation])["decision"] == "ERROR"


def test_noncritical_threshold_does_not_turn_one_failure_into_automatic_rejection():
    requirements = [Requirement(id="quality", description="Useful", pass_rate=0.5)]
    observations = [
        {"id": "one", "requirement_id": "quality", "case_id": "one", "passed": True, "error": None},
        {
            "id": "two",
            "requirement_id": "quality",
            "case_id": "two",
            "passed": False,
            "error": None,
        },
    ]
    assert decide(requirements, ["one", "two"], observations)["decision"] == "PASS"
