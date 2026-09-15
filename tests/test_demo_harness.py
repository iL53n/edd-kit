import copy
import importlib.util

from deepeval.test_case import LLMTestCase

from edd_kit.backend import grade
from edd_kit.scaffold import init_project, prepare_change


def test_demo_rejects_unauthorized_mutation_even_when_final_state_is_restored(tmp_path):
    init_project(tmp_path, "none")
    prepare_change(tmp_path, "orders", "Cancel owned orders", "cancellation")
    spec = importlib.util.spec_from_file_location("demo", tmp_path / "evals/orders/suite.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = module.build_suite()
    case = next(case for case in suite.cases if case.case_id == "reject-other-owner")
    active = {"owner": "bob", "status": "active"}
    cancelled = {"owner": "bob", "status": "cancelled"}
    observation = LLMTestCase(
        input=case.test_case.input,
        actual_output="That order does not belong to you.",
        metadata={
            "case_id": case.case_id,
            "fixture": case.fixture,
            "state_after": copy.deepcopy(case.fixture["orders"]),
            "events": [
                {"order_id": "order-b", "before": active, "after": cancelled},
                {"order_id": "order-b", "before": cancelled, "after": active},
            ],
        },
    )
    result = grade(suite.metrics["preserve-other-customers-orders"], observation)
    assert result["error"] is None
    assert result["passed"] is False
