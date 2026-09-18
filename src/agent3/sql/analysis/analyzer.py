from __future__ import annotations

from sqlglot import exp, parse, parse_one
from sqlglot.errors import ParseError

from agent3.sql.analysis.models import SQLAnalysis, SQLColumnRef

_DIALECTS = {"maxcompute": "hive", "odps": "hive", "dataworks": "hive"}


class SQLAnalysisError(ValueError):
    pass


def _dialect(name: str) -> str:
    return _DIALECTS.get(name.casefold(), name)


def _table_name(table: exp.Table) -> str:
    parts = [part for part in (table.catalog, table.db, table.name) if part]
    return ".".join(parts)


class SQLAnalyzer:
    """Thin SQLGlot adapter migrated from the Agent3.0 SQL-analysis contract.

    The adapter owns dialect mapping and parse-error translation only. It deliberately
    exposes both single-statement parsing and program parsing so safety gates can fail
    closed on multi-statement input instead of inspecting only the first statement.
    """

    def analyze(self, sql: str, *, dialect: str = "maxcompute") -> SQLAnalysis:
        tree = self.parse(sql, dialect=dialect)
        tables = tuple(sorted({_table_name(t) for t in tree.find_all(exp.Table)}))
        columns = tuple(SQLColumnRef(table=(c.table or None), name=c.name) for c in tree.find_all(exp.Column))
        where = tree.find(exp.Where)
        return SQLAnalysis(
            sql=sql,
            dialect=dialect,
            statement_type=tree.key.upper(),
            tables=tables,
            columns=columns,
            where_sql=where.sql(dialect=_dialect(dialect)) if where else None,
            normalized_sql=tree.sql(dialect=_dialect(dialect), pretty=False),
        )

    def parse_program(self, sql: str, *, dialect: str = "maxcompute") -> tuple[exp.Expression, ...]:
        normalized = sql.strip()
        if not normalized:
            raise SQLAnalysisError("SQL cannot be empty")
        try:
            statements = tuple(parse(normalized, read=_dialect(dialect)))
        except ParseError as exc:
            raise SQLAnalysisError(str(exc)) from exc
        if not statements:
            raise SQLAnalysisError("SQL cannot be empty")
        return statements

    def parse(self, sql: str, *, dialect: str = "maxcompute") -> exp.Expression:
        normalized = sql.strip()
        if not normalized:
            raise SQLAnalysisError("SQL cannot be empty")
        try:
            return parse_one(normalized, read=_dialect(dialect))
        except ParseError as exc:
            raise SQLAnalysisError(str(exc)) from exc
