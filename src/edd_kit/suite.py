"""Small Python interface joining native DeepEval objects to requirement identities."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Case:
    case_id: str
    test_case: Any
    requirements: tuple[str, ...]
    profiles: tuple[str, ...] = ("dev", "acceptance")
    fixture: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    expected_behavior: str = ""
    acceptable_alternatives: tuple[str, ...] = ()
    unacceptable_behaviors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Control:
    control_id: str
    requirement_id: str
    test_case: Any
    expected_pass: bool
    source: str
    reviewed_by: str | None = None
    partition: str = "validation"
    case_id: str | None = None
    rationale: str = ""
    contributed_by: str = ""
    independent: bool = False


@dataclass(frozen=True)
class Suite:
    cases: list[Case]
    controls: list[Control]
    metrics: dict[str, Callable[[], Any]]
