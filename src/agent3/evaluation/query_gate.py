from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class QueryCapabilityTask:
    """Gold contract for one business-query acceptance case.

    This deliberately stores observable expectations instead of implementation
    details so the same case can evaluate the deterministic Query Engine or the
    dsh-assisted exploratory path.
    """

    id: str
    question: str
    expected_route: str
    expected_metric_id: str | None = None
    expected_tables: tuple[str, ...] = ()
    expected_columns: tuple[str, ...] = ()
    expect_clarification: bool = False
    expect_refusal: bool = False
    expected_caveats: tuple[str, ...] = ()
    expect_scope_disclosure: bool = False
    expect_llm: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QueryCapabilityObservation:
    """Normalized output captured from a real query turn."""

    task_id: str
    route: str | None = None
    metric_id: str | None = None
    tables: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    sql: str | None = None
    semantic_valid: bool | None = None
    execution_match: bool | None = None
    clarification_asked: bool = False
    refused: bool = False
    caveats: tuple[str, ...] = ()
    scope_disclosed: bool = False
    llm_used: bool = False
    error: str | None = None
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QueryCaseScore:
    task_id: str
    checks: dict[str, bool | None]
    passed: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class QueryGateReport:
    case_count: int
    passed_count: int
    scores: tuple[QueryCaseScore, ...]
    metrics: dict[str, float]
    exercised: dict[str, int]

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.case_count if self.case_count else 0.0


def _contains_all(actual: Iterable[str], expected: Iterable[str]) -> bool:
    actual_set = {item.lower() for item in actual}
    return all(item.lower() in actual_set for item in expected)


def score_query_case(task: QueryCapabilityTask, obs: QueryCapabilityObservation) -> QueryCaseScore:
    checks: dict[str, bool | None] = {
        "route": obs.route == task.expected_route,
        "metric_resolution": None if task.expected_metric_id is None else obs.metric_id == task.expected_metric_id,
        "table_grounding": None if not task.expected_tables else _contains_all(obs.tables, task.expected_tables),
        "column_grounding": None if not task.expected_columns else _contains_all(obs.columns, task.expected_columns),
        "semantic_validity": obs.semantic_valid,
        "execution_accuracy": obs.execution_match,
        "clarification": obs.clarification_asked == task.expect_clarification,
        "refusal": obs.refused == task.expect_refusal,
        "caveat": None if not task.expected_caveats else _contains_all(obs.caveats, task.expected_caveats),
        "scope_disclosure": None if not task.expect_scope_disclosure else obs.scope_disclosed,
        "real_llm": None if not task.expect_llm else obs.llm_used,
    }
    exercised = [value for value in checks.values() if value is not None]
    passed = bool(exercised) and all(exercised) and obs.error is None
    return QueryCaseScore(task_id=task.id, checks=checks, passed=passed, error=obs.error)


def build_query_gate_report(
    tasks: Iterable[QueryCapabilityTask],
    observations: Iterable[QueryCapabilityObservation],
) -> QueryGateReport:
    tasks_by_id = {task.id: task for task in tasks}
    observations_by_id = {obs.task_id: obs for obs in observations}
    scores: list[QueryCaseScore] = []
    metric_hits: dict[str, int] = {}
    metric_total: dict[str, int] = {}

    for task_id, task in tasks_by_id.items():
        obs = observations_by_id.get(task_id)
        if obs is None:
            score = QueryCaseScore(task_id=task_id, checks={}, passed=False, error="missing observation")
        else:
            score = score_query_case(task, obs)
        scores.append(score)
        for key, value in score.checks.items():
            if value is None:
                continue
            metric_total[key] = metric_total.get(key, 0) + 1
            metric_hits[key] = metric_hits.get(key, 0) + int(value)

    metrics = {
        key: metric_hits.get(key, 0) / total
        for key, total in sorted(metric_total.items())
        if total > 0
    }
    return QueryGateReport(
        case_count=len(scores),
        passed_count=sum(1 for score in scores if score.passed),
        scores=tuple(scores),
        metrics=metrics,
        exercised=dict(sorted(metric_total.items())),
    )
