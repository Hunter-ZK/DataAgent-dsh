from __future__ import annotations

from typing import Any
from agent3.adapters.mcp.authz import AuthzProvider
from agent3.semantic.models import MandatoryFilter, QueryIR
from agent3.services.core import Agent3Core


class MCPToolAdapter:
    """Thin protocol projection. No business rules belong here."""
    def __init__(self, core: Agent3Core, authz_provider: AuthzProvider) -> None:
        self._core = core
        self._authz = authz_provider

    def search_tables(self, query: str, limit: int = 8) -> dict[str, Any]:
        return self._core.search_tables(self._authz(), query, limit=limit)

    def get_schema(self, table_name: str) -> dict[str, Any]:
        return self._core.get_schema(self._authz(), table_name)

    def get_semantic_model(self, metric_id: str) -> dict[str, Any]:
        return self._core.get_semantic_model(self._authz(), metric_id)

    def resolve_metric(self, phrase: str) -> dict[str, Any]:
        return self._core.resolve_metric(self._authz(), phrase)

    def search_verified_sql(self, query: str, limit: int = 5) -> dict[str, Any]:
        return self._core.search_verified_sql(self._authz(), query, limit=limit)

    def validate_sql(self, sql: str, dialect: str = "maxcompute", metric_id: str | None = None) -> dict[str, Any]:
        return self._core.validate_sql(self._authz(), sql, dialect=dialect, metric_id=metric_id)

    def explain_sql(self, sql: str, dialect: str = "maxcompute") -> dict[str, Any]:
        return self._core.explain_sql(self._authz(), sql, dialect=dialect)

    def compile_query(self, metric_id: str, dimensions: list[str] | None = None, time_values: list[str] | None = None, filters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        ir = QueryIR(
            metric_id=metric_id,
            dimensions=tuple(dimensions or ()),
            time_values=tuple(time_values or ()),
            filters=tuple(MandatoryFilter(field=i["field"], op=i["op"], value=i["value"]) for i in (filters or ())),
        )
        return self._core.compile_query(self._authz(), ir)
