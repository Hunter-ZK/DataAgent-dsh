from __future__ import annotations

from sqlglot import exp

from agent3.contracts.authz import AuthzContext
from agent3.metadata.provider import MetadataProvider
from agent3.semantic.models import Additivity, MandatoryFilter
from agent3.semantic.registry import SemanticRegistry
from agent3.sql.analysis.analyzer import SQLAnalysisError, SQLAnalyzer
from agent3.sql.validation.models import Severity, ValidationIssue, ValidationResult


class SQLValidator:
    """Deterministic quality gate migrated from Agent3.0's trusted-SQL direction."""
    def __init__(self, metadata: MetadataProvider, semantics: SemanticRegistry) -> None:
        self._metadata = metadata
        self._semantics = semantics
        self._analyzer = SQLAnalyzer()

    def validate(self, authz: AuthzContext, sql: str, *, dialect: str = "maxcompute", metric_id: str | None = None) -> ValidationResult:
        issues: list[ValidationIssue] = []
        try:
            analysis = self._analyzer.analyze(sql, dialect=dialect)
            tree = self._analyzer.parse(sql, dialect=dialect)
        except SQLAnalysisError as exc:
            return ValidationResult(False, dialect, (ValidationIssue("SQL_PARSE_ERROR", Severity.ERROR, str(exc), "检查 SQL 语法与方言"),))

        destructive = (exp.Drop, exp.Delete, exp.Update, exp.Alter, exp.Create, exp.Insert)
        if isinstance(tree, destructive):
            issues.append(ValidationIssue("WRITE_STATEMENT", Severity.ERROR, f"validate_sql 默认只接受只读查询，检测到 {analysis.statement_type}", "DDL/DML 必须走受控写操作工具"))

        resolved_tables = []
        for table_name in analysis.tables:
            table = self._metadata.get_table(authz, table_name)
            if table is None:
                issues.append(ValidationIssue("UNKNOWN_TABLE", Severity.ERROR, f"表不存在或元数据不可见: {table_name}", "先调用 search_tables/get_schema 选择已授权表", {"table": table_name}))
            else:
                resolved_tables.append(table)

        if resolved_tables:
            for ref in analysis.columns:
                if ref.name == "*":
                    continue
                if not any(table.column(ref.name) is not None for table in resolved_tables):
                    issues.append(ValidationIssue("UNKNOWN_COLUMN", Severity.ERROR, f"字段不存在: {ref.name}", "调用 get_schema 获取真实字段", {"column": ref.name}))
            where_columns = {c.name.casefold() for c in tree.find(exp.Where).find_all(exp.Column)} if tree.find(exp.Where) else set()
            for table in resolved_tables:
                if table.partition_fields and not any(p.casefold() in where_columns for p in table.partition_fields):
                    issues.append(ValidationIssue("NO_PARTITION_FILTER", Severity.WARNING, f"{table.full_name} 未命中分区字段 {', '.join(table.partition_fields)}", "增加明确分区过滤，避免无界扫描"))

        if metric_id:
            issues.extend(self._validate_metric(authz, tree, metric_id))

        return ValidationResult(valid=not any(i.severity is Severity.ERROR for i in issues), dialect=dialect, issues=tuple(issues), normalized_sql=analysis.normalized_sql)

    def _validate_metric(self, authz: AuthzContext, tree: exp.Expression, metric_id: str) -> list[ValidationIssue]:
        metric = self._semantics.get(authz, metric_id)
        if metric is None:
            return [ValidationIssue("UNKNOWN_METRIC", Severity.ERROR, f"未知指标: {metric_id}")]
        issues: list[ValidationIssue] = []
        functions = [node for node in tree.walk() if isinstance(node, exp.AggFunc)]
        matched_agg = False
        for fn in functions:
            if fn.key.casefold() == metric.aggregation.casefold():
                cols = {c.name.casefold() for c in fn.find_all(exp.Column)}
                if metric.measure.casefold() in cols:
                    matched_agg = True
                    break
        if not matched_agg:
            issues.append(ValidationIssue("METRIC_MISMATCH", Severity.ERROR, f"指标 {metric.id} 要求 {metric.aggregation}({metric.measure})", f"使用 {metric.aggregation}({metric.measure})", {"metric_id": metric.id, "aggregation": metric.aggregation, "measure": metric.measure}))

        where = tree.find(exp.Where)
        for required in metric.mandatory_filters:
            if not self._has_filter(where, required):
                issues.append(ValidationIssue("MISSING_MANDATORY_FILTER", Severity.ERROR, f"指标 {metric.id} 缺少强制过滤 {required.field} {required.op} {required.value}", "按语义模型补充强制过滤", {"metric_id": metric.id, "field": required.field}))

        if metric.additivity_time is Additivity.NON_ADDITIVE and not self._has_single_equality(where, "dt"):
            issues.append(ValidationIssue("NON_ADDITIVE_OVER_TIME", Severity.ERROR, f"指标 {metric.id} 为时间非可加快照指标，必须限定单个 dt", "选择单个期末快照日期；不要跨日期 SUM", {"metric_id": metric.id}))
        return issues

    @staticmethod
    def _has_filter(where: exp.Where | None, required: MandatoryFilter) -> bool:
        if where is None:
            return False
        classes = {"eq": exp.EQ, "ne": exp.NEQ, "gt": exp.GT, "gte": exp.GTE, "lt": exp.LT, "lte": exp.LTE}
        target = classes.get(required.op)
        if target is None:
            return False
        for node in where.find_all(target):
            left = node.this
            right = node.expression
            if isinstance(left, exp.Column) and left.name.casefold() == required.field.casefold():
                value = right.this if isinstance(right, exp.Literal) else None
                if str(value) == str(required.value):
                    return True
        return False

    @staticmethod
    def _has_single_equality(where: exp.Where | None, field: str) -> bool:
        if where is None:
            return False
        return any(isinstance(node.this, exp.Column) and node.this.name.casefold() == field.casefold() and isinstance(node.expression, exp.Literal) for node in where.find_all(exp.EQ))
