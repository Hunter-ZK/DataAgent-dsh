from __future__ import annotations

import re
from dataclasses import dataclass

from agent3.contracts.authz import AuthzContext
from agent3.metadata.provider import MetadataProvider
from agent3.query.models import (
    GroundedQuery,
    QueryClarification,
    QueryGroundingEvidence,
    QueryRefusal,
    QueryUnderstandingOutcome,
    QueryUnderstandingStatus,
)
from agent3.routing.models import TaskContract, TaskType
from agent3.semantic.models import Additivity, MandatoryFilter, MetricDefinition, QueryIR
from agent3.semantic.registry import SemanticRegistry

_DATE_ISO = re.compile(r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")
_DATE_CN = re.compile(r"(?<!\d)(20\d{2})年(\d{1,2})月(\d{1,2})日")
_EXPLORATORY_MARKERS = ("为什么", "原因", "分析", "解释", "驱动因素", "影响因素", "异常")
_GROUP_PREFIXES = ("按", "分", "各", "每个", "不同")


@dataclass(frozen=True, slots=True)
class _MetricMatch:
    metric: MetricDefinition
    term: str


class DeterministicQuestionInterpreter:
    """Conservative business-question interpreter for the Query Engine fast path.

    It never invents semantic or physical names. A question reaches READY only
    when metric, source table, dimensions, filters and snapshot semantics are
    grounded in approved Semantic/Metadata assets. Everything else becomes an
    explicit clarification, refusal or exploratory task for dsh.
    """

    def __init__(self, registry: SemanticRegistry, metadata: MetadataProvider) -> None:
        self._registry = registry
        self._metadata = metadata

    def interpret(
        self,
        authz: AuthzContext,
        question: str,
        *,
        context_metric_id: str | None = None,
    ) -> QueryUnderstandingOutcome:
        objective = question.strip()
        if not objective:
            return self._refusal(objective, "empty question")

        metric_matches = self._match_metrics(authz, objective)
        if context_metric_id and not metric_matches:
            metric = self._registry.get(authz, context_metric_id)
            if metric is not None:
                metric_matches = (_MetricMatch(metric, context_metric_id),)

        metric_ids = {item.metric.id for item in metric_matches}
        if len(metric_ids) > 1:
            options = tuple(sorted(metric_ids))
            return self._clarification(
                objective,
                question=f"你的问题同时命中了多个指标：{', '.join(options)}。请确认要查询哪个指标？",
                missing_context=("metric",),
                reason="multiple semantic metrics matched the question",
                evidence=QueryGroundingEvidence(
                    recognized_terms=tuple(item.term for item in metric_matches),
                    semantic_coverage=0.0,
                ),
            )
        if not metric_matches:
            return self._refusal(
                objective,
                "no approved metric matched the question; refusing to invent a metric or table",
            )

        match = max(metric_matches, key=lambda item: len(item.term))
        metric = match.metric
        table = self._metadata.get_table(authz, metric.source_entity)
        if table is None:
            return self._refusal(
                objective,
                f"approved metric {metric.id!r} points to unavailable source entity {metric.source_entity!r}",
                metric=metric,
                recognized=(match.term,),
            )
        if table.column(metric.measure) is None:
            return self._refusal(
                objective,
                f"metric measure {metric.measure!r} is absent from authoritative metadata",
                metric=metric,
                recognized=(match.term,),
            )

        recognized = [match.term]
        dimensions: list[str] = []
        filters: list[MandatoryFilter] = []
        physical_columns = {metric.measure}

        for dimension in self._registry.all_dimensions(authz):
            if metric.valid_dimensions and dimension.field not in metric.valid_dimensions:
                continue
            if table.column(dimension.field) is None:
                continue
            names = (dimension.id, dimension.name, dimension.field, *dimension.aliases)
            grouping_term = self._grouping_term(objective, names)
            if grouping_term is not None:
                dimensions.append(dimension.field)
                physical_columns.add(dimension.field)
                recognized.append(grouping_term)

            matched_values = []
            for item in dimension.values:
                value_terms = (item.name, *item.aliases)
                for term in value_terms:
                    if term and term.casefold() in objective.casefold():
                        matched_values.append(item)
                        recognized.append(term)
                        break
            unique_values = {item.value for item in matched_values}
            if len(unique_values) > 1:
                return self._clarification(
                    objective,
                    question=f"问题中出现了多个{dimension.name}值，请确认本次查询范围。",
                    missing_context=(dimension.id,),
                    reason=f"multiple values matched dimension {dimension.id}",
                    evidence=QueryGroundingEvidence(
                        metric_id=metric.id,
                        source_entity=metric.source_entity,
                        physical_columns=tuple(sorted(physical_columns)),
                        recognized_terms=tuple(dict.fromkeys(recognized)),
                        caveats=(metric.caveats,) if metric.caveats else (),
                        semantic_coverage=0.7,
                    ),
                )
            if len(unique_values) == 1:
                value = next(iter(unique_values))
                filters.append(MandatoryFilter(dimension.field, "eq", value))
                physical_columns.add(dimension.field)

        time_values = self._extract_dates(objective)
        if time_values:
            if table.column(metric.time_field) is None:
                return self._refusal(
                    objective,
                    f"metric time field {metric.time_field!r} is absent from authoritative metadata",
                    metric=metric,
                    recognized=tuple(recognized),
                )
            physical_columns.add(metric.time_field)
            recognized.extend(time_values)

        if metric.additivity_time is Additivity.NON_ADDITIVE:
            if not time_values:
                return self._clarification(
                    objective,
                    question=f"{metric.name}是期末/快照指标，请确认要查询的具体日期。",
                    missing_context=("time",),
                    reason="non-additive time metric requires an explicit snapshot date",
                    evidence=self._evidence(metric, physical_columns, recognized, 0.8),
                )
            if len(time_values) > 1:
                return self._clarification(
                    objective,
                    question=f"{metric.name}不能跨多个快照日期直接求和。请确认单个日期，或改为明确的趋势分析。",
                    missing_context=("time_aggregation",),
                    reason="multiple snapshots require an explicit time-series intent",
                    evidence=self._evidence(metric, physical_columns, recognized, 0.8),
                )

        if any(marker in objective for marker in _EXPLORATORY_MARKERS):
            contract = TaskContract(
                task_type=TaskType.EXPLORATORY_ANALYSIS,
                objective=objective,
                required_capabilities=("analysis",),
                ir_valid=True,
                semantic_coverage=1.0,
            )
            return GroundedQuery(
                status=QueryUnderstandingStatus.EXPLORATORY,
                task_contract=contract,
                query_ir=QueryIR(
                    metric_id=metric.id,
                    dimensions=tuple(dict.fromkeys(dimensions)),
                    filters=tuple(filters),
                    time_values=time_values,
                ),
                evidence=self._evidence(metric, physical_columns, recognized, 1.0),
                llm_used=False,
            )

        ir = QueryIR(
            metric_id=metric.id,
            dimensions=tuple(dict.fromkeys(dimensions)),
            filters=tuple(filters),
            time_values=time_values,
        )
        contract = TaskContract(
            task_type=TaskType.STANDARD_QUERY,
            objective=objective,
            required_capabilities=("semantic_query",),
            ir_valid=True,
            semantic_coverage=1.0,
        )
        return GroundedQuery(
            status=QueryUnderstandingStatus.READY,
            task_contract=contract,
            query_ir=ir,
            evidence=self._evidence(metric, physical_columns, recognized, 1.0),
            llm_used=False,
        )

    def _match_metrics(self, authz: AuthzContext, question: str) -> tuple[_MetricMatch, ...]:
        folded = question.casefold()
        matches: list[_MetricMatch] = []
        for metric in self._registry.all(authz):
            for term in (metric.id, metric.name, *metric.aliases):
                if term and term.casefold() in folded:
                    matches.append(_MetricMatch(metric, term))
                    break
        return tuple(matches)

    @staticmethod
    def _grouping_term(question: str, names: tuple[str, ...]) -> str | None:
        folded = question.casefold()
        for name in names:
            if not name:
                continue
            n = name.casefold()
            if any((prefix + n) in folded for prefix in _GROUP_PREFIXES):
                return name
        return None

    @staticmethod
    def _extract_dates(question: str) -> tuple[str, ...]:
        values: list[str] = []
        for regex in (_DATE_ISO, _DATE_CN):
            for match in regex.finditer(question):
                year, month, day = (int(value) for value in match.groups())
                normalized = f"{year:04d}-{month:02d}-{day:02d}"
                if normalized not in values:
                    values.append(normalized)
        return tuple(values)

    @staticmethod
    def _evidence(
        metric: MetricDefinition,
        physical_columns: set[str],
        recognized: list[str] | tuple[str, ...],
        coverage: float,
    ) -> QueryGroundingEvidence:
        return QueryGroundingEvidence(
            metric_id=metric.id,
            source_entity=metric.source_entity,
            physical_columns=tuple(sorted(physical_columns)),
            recognized_terms=tuple(dict.fromkeys(recognized)),
            caveats=(metric.caveats,) if metric.caveats else (),
            semantic_coverage=coverage,
        )

    def _clarification(
        self,
        objective: str,
        *,
        question: str,
        missing_context: tuple[str, ...],
        reason: str,
        evidence: QueryGroundingEvidence,
    ) -> QueryClarification:
        return QueryClarification(
            status=QueryUnderstandingStatus.NEED_CLARIFICATION,
            task_contract=TaskContract(
                task_type=TaskType.STANDARD_QUERY,
                objective=objective,
                required_capabilities=("semantic_query",),
                ir_valid=False,
                semantic_coverage=evidence.semantic_coverage,
            ),
            question=question,
            missing_context=missing_context,
            reason=reason,
            evidence=evidence,
        )

    def _refusal(
        self,
        objective: str,
        reason: str,
        *,
        metric: MetricDefinition | None = None,
        recognized: tuple[str, ...] = (),
    ) -> QueryRefusal:
        evidence = QueryGroundingEvidence(
            metric_id=metric.id if metric else None,
            source_entity=metric.source_entity if metric else None,
            recognized_terms=recognized,
            caveats=(metric.caveats,) if metric and metric.caveats else (),
            semantic_coverage=0.0,
        )
        return QueryRefusal(
            status=QueryUnderstandingStatus.REFUSED,
            task_contract=TaskContract(
                task_type=TaskType.STANDARD_QUERY,
                objective=objective,
                required_capabilities=("semantic_query",),
                ir_valid=False,
                semantic_coverage=0.0,
            ),
            reason=reason,
            evidence=evidence,
        )
