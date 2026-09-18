from agent3.routing.models import Route, TaskContract, TaskType
from agent3.routing.router import TaskRouter


def test_standard_query_routes_deterministically() -> None:
    router = TaskRouter(semantic_threshold=0.85)
    assert router.route(TaskContract(TaskType.STANDARD_QUERY, "余额", ir_valid=True, semantic_coverage=0.9)) is Route.QUERY_ENGINE


def test_exploratory_or_low_coverage_goes_agentic() -> None:
    router = TaskRouter()
    assert router.route(TaskContract(TaskType.EXPLORATORY_ANALYSIS, "为什么下降", ir_valid=True, semantic_coverage=1.0)) is Route.AGENTIC_ANALYSIS
    assert router.route(TaskContract(TaskType.STANDARD_QUERY, "余额", ir_valid=True, semantic_coverage=0.5)) is Route.AGENTIC_ANALYSIS
