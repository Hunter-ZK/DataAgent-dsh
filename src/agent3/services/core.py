from __future__ import annotations

from dataclasses import asdict
from typing import Any
from agent3.contracts.authz import AuthzContext
from agent3.knowledge.injection import scan_retrieved_evidence
from agent3.knowledge.verified_sql import InMemoryVerifiedSQLStore
from agent3.metadata.provider import MetadataProvider
from agent3.semantic.compiler import SemanticCompiler
from agent3.semantic.models import QueryIR
from agent3.semantic.registry import SemanticRegistry
from agent3.sql.analysis.analyzer import SQLAnalysisError, SQLAnalyzer
from agent3.sql.validation.validator import SQLValidator


class Agent3Core:
    """Harness-agnostic service facade. Every public method takes AuthzContext first."""
    def __init__(self, *, metadata: MetadataProvider, semantics: SemanticRegistry, verified_sql: InMemoryVerifiedSQLStore | None = None) -> None:
        self.metadata = metadata
        self.semantics = semantics
        self.verified_sql = verified_sql or InMemoryVerifiedSQLStore()
        self.validator = SQLValidator(metadata, semantics)
        self.analyzer = SQLAnalyzer()
        self.compiler = SemanticCompiler(semantics, metadata)

    def search_tables(self, authz: AuthzContext, query: str, *, limit: int = 8) -> dict[str, Any]:
        tables = self.metadata.search_tables(authz, query, limit=limit)
        return {"tables": [{"full_name": t.full_name, "description": t.description, "partition_fields": list(t.partition_fields), "row_count_estimate": t.row_count_estimate, "warnings": list(scan_retrieved_evidence(t.description))} for t in tables]}

    def get_schema(self, authz: AuthzContext, table_name: str) -> dict[str, Any]:
        table = self.metadata.get_table(authz, table_name)
        if table is None:
            return {"found": False, "table": table_name}
        return {"found": True, "table": table.full_name, "description": table.description, "partition_fields": list(table.partition_fields), "columns": [asdict(c) for c in table.columns], "warnings": list(scan_retrieved_evidence("\n".join([table.description, *(c.description for c in table.columns)])))}

    def get_semantic_model(self, authz: AuthzContext, metric_id: str) -> dict[str, Any]:
        metric = self.semantics.get(authz, metric_id)
        return {"found": metric is not None, "metric": asdict(metric) if metric else None}

    def resolve_metric(self, authz: AuthzContext, phrase: str) -> dict[str, Any]:
        metric = self.semantics.resolve(authz, phrase)
        return {"resolved": metric is not None, "metric": asdict(metric) if metric else None}

    def search_verified_sql(self, authz: AuthzContext, query: str, *, limit: int = 5) -> dict[str, Any]:
        return {"items": [asdict(item) for item in self.verified_sql.search(authz, query, limit=limit)]}

    def validate_sql(self, authz: AuthzContext, sql: str, *, dialect: str = "maxcompute", metric_id: str | None = None) -> dict[str, Any]:
        return self.validator.validate(authz, sql, dialect=dialect, metric_id=metric_id).to_dict()

    def explain_sql(self, authz: AuthzContext, sql: str, *, dialect: str = "maxcompute") -> dict[str, Any]:
        _ = authz
        try:
            analysis = self.analyzer.analyze(sql, dialect=dialect)
        except SQLAnalysisError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "statement_type": analysis.statement_type, "tables": list(analysis.tables), "columns": [{"table": c.table, "name": c.name} for c in analysis.columns], "where": analysis.where_sql, "normalized_sql": analysis.normalized_sql, "cost_estimate": None, "cost_estimate_status": "not_available_without_execution_backend"}

    def compile_query(self, authz: AuthzContext, ir: QueryIR) -> dict[str, Any]:
        sql = self.compiler.compile(authz, ir)
        validation = self.validator.validate(authz, sql, metric_id=ir.metric_id)
        return {"sql": sql, "validation": validation.to_dict()}

    def register_verified_sql(self, authz: AuthzContext, *, question: str, sql: str, tables: tuple[str, ...], metrics: tuple[str, ...] = (), human_approved: bool = False) -> dict[str, Any]:
        if not human_approved:
            raise PermissionError("register_verified_sql requires explicit human approval")
        return asdict(self.verified_sql.register(authz, question=question, sql_text=sql, tables=tables, metrics=metrics))

    def submit_ddl(self, authz: AuthzContext, ddl: str) -> dict[str, Any]:
        _ = authz, ddl
        return {"accepted": False, "approval_required": True, "execution_enabled": False, "reason": "Production DDL execution is outside V1 and cannot be bypassed by an adapter."}
