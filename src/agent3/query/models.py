from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agent3.routing.models import TaskContract
from agent3.semantic.models import MandatoryFilter, QueryIR


class QueryUnderstandingStatus(StrEnum):
    READY = "ready"
    NEED_CLARIFICATION = "need_clarification"
    EXPLORATORY = "exploratory"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class QueryGroundingEvidence:
    metric_id: str | None = None
    source_entity: str | None = None
    physical_columns: tuple[str, ...] = ()
    recognized_terms: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    semantic_coverage: float = 0.0


@dataclass(frozen=True, slots=True)
class GroundedQuery:
    status: QueryUnderstandingStatus
    task_contract: TaskContract
    query_ir: QueryIR | None
    evidence: QueryGroundingEvidence
    llm_used: bool = False

    def __post_init__(self) -> None:
        if self.status is QueryUnderstandingStatus.READY and self.query_ir is None:
            raise ValueError("ready query understanding requires QueryIR")


@dataclass(frozen=True, slots=True)
class QueryClarification:
    status: QueryUnderstandingStatus
    task_contract: TaskContract
    question: str
    missing_context: tuple[str, ...]
    reason: str
    evidence: QueryGroundingEvidence

    def __post_init__(self) -> None:
        if self.status is not QueryUnderstandingStatus.NEED_CLARIFICATION:
            raise ValueError("QueryClarification status must be need_clarification")
        if not self.question.strip():
            raise ValueError("clarification question must not be empty")


@dataclass(frozen=True, slots=True)
class QueryRefusal:
    status: QueryUnderstandingStatus
    task_contract: TaskContract
    reason: str
    evidence: QueryGroundingEvidence

    def __post_init__(self) -> None:
        if self.status is not QueryUnderstandingStatus.REFUSED:
            raise ValueError("QueryRefusal status must be refused")


@dataclass(frozen=True, slots=True)
class QueryFilterCandidate:
    field: str
    op: str
    value: str

    def to_filter(self) -> MandatoryFilter:
        return MandatoryFilter(self.field, self.op, self.value)


QueryUnderstandingOutcome = GroundedQuery | QueryClarification | QueryRefusal
