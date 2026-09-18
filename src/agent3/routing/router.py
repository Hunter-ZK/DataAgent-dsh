from agent3.routing.models import Route, TaskContract, TaskType


class TaskRouter:
    """Program-owned routing. The model may parse a contract but cannot choose a route."""
    def __init__(self, *, semantic_threshold: float = 0.85) -> None:
        self._threshold = semantic_threshold

    def route(self, contract: TaskContract) -> Route:
        if contract.task_type is TaskType.STANDARD_QUERY and contract.ir_valid and contract.semantic_coverage >= self._threshold:
            return Route.QUERY_ENGINE
        return Route.AGENTIC_ANALYSIS
