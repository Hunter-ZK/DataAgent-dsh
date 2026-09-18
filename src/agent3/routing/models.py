from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TaskType(StrEnum):
    STANDARD_QUERY = "standard_query"
    EXPLORATORY_ANALYSIS = "exploratory_analysis"
    WAREHOUSE_DEVELOPMENT = "warehouse_development"


class Route(StrEnum):
    QUERY_ENGINE = "query_engine"
    AGENTIC_ANALYSIS = "agentic_analysis"


@dataclass(frozen=True, slots=True)
class TaskContract:
    task_type: TaskType
    objective: str
    required_capabilities: tuple[str, ...] = ()
    ir_valid: bool = False
    semantic_coverage: float = 0.0
