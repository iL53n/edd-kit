"""Validated on-disk configuration. Grading logic stays in native Python metrics."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
Text = Annotated[str, Field(min_length=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Requirement(Model):
    id: Identifier
    description: Text
    critical: bool = False
    pass_rate: float = Field(default=1.0, gt=0, le=1)
    min_cases: int = Field(default=1, ge=1, le=100000, strict=True)


class Profile(Model):
    trials: int = Field(default=1, ge=1, le=100, strict=True)
    grader_repetitions: int = Field(default=1, ge=1, le=100, strict=True)
    max_observations: int = Field(default=1000, ge=1, le=1000000, strict=True)
    max_cost_usd: float = Field(default=0, ge=0)
    timeout_seconds: float = Field(default=120, gt=0, le=86400)


class Target(Model):
    kind: Literal["application", "stub", "reference"]
    command: list[Text] = Field(min_length=1)
    files: list[Text] = Field(min_length=1)
    env: list[Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]] = []
    timeout_seconds: float = Field(default=30, gt=0, le=3600)
    version: str | None = None


class Contract(Model):
    schema_version: Literal[1]
    change: Identifier
    title: Text
    suite: Text = "suite.py:build_suite"
    artifacts: list[Text] = []
    requirements: list[Requirement] = Field(min_length=1)
    profiles: dict[Literal["dev", "acceptance"], Profile]
    targets: dict[Identifier, Target] = Field(min_length=1)
    evaluator_env: list[Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]] = []

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @model_validator(mode="after")
    def coherent(self):
        ids = [requirement.id for requirement in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("Requirement IDs must be unique")
        if set(self.profiles) != {"dev", "acceptance"}:
            raise ValueError("Both dev and acceptance profiles are required")
        if ":" not in self.suite or not self.suite.split(":", 1)[0].endswith(".py"):
            raise ValueError("suite must be a relative Python file:function entrypoint")
        return self
