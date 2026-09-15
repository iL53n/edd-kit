import pytest

from edd_kit.models import Contract


def example_contract():
    return {
        "schema_version": 1,
        "change": "cancellation",
        "title": "Cancel eligible orders",
        "suite": "suite.py:build_suite",
        "requirements": [{"id": "ownership", "description": "Never change another user's order"}],
        "profiles": {"dev": {}, "acceptance": {}},
        "targets": {
            "candidate": {
                "kind": "application",
                "command": ["python3", "app.py"],
                "files": ["app.py"],
            }
        },
    }


def test_contract_requires_unique_requirements_and_both_execution_profiles():
    data = example_contract()
    assert Contract.model_validate(data).requirements[0].critical is False
    data["requirements"].append(data["requirements"][0])
    with pytest.raises(ValueError, match="unique"):
        Contract.model_validate(data)
    data = example_contract()
    del data["profiles"]["acceptance"]
    with pytest.raises(ValueError, match="acceptance"):
        Contract.model_validate(data)


@pytest.mark.parametrize("field,value", [("critical", "false"), ("pass_rate", True)])
def test_contract_does_not_coerce_invalid_policy_types(field, value):
    data = example_contract()
    data["requirements"][0][field] = value
    with pytest.raises(ValueError):
        Contract.model_validate(data)


@pytest.mark.parametrize("version", [True, 1.0, "1"])
def test_contract_version_is_an_integer_not_a_coercible_value(version):
    data = example_contract()
    data["schema_version"] = version
    with pytest.raises(ValueError):
        Contract.model_validate(data)
