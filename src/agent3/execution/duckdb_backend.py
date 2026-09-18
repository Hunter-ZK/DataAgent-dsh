from __future__ import annotations

import duckdb
from agent3.contracts.authz import AuthzContext
from agent3.execution.models import ExecutionLimits, ResultSet
from agent3.sql.analysis.analyzer import SQLAnalyzer


class ExecutionError(RuntimeError):
    pass


class ExecutionLimitExceeded(ExecutionError):
    pass


class DuckDBExecutionBackend:
    """Stage-0 evaluation backend. It is intentionally not exposed as an agent tool."""
    def __init__(self, connection: duckdb.DuckDBPyConnection | None = None) -> None:
        self._conn = connection or duckdb.connect(":memory:")
        self._analyzer = SQLAnalyzer()

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    def execute(self, authz: AuthzContext, sql: str, *, limits: ExecutionLimits) -> ResultSet:
        _ = authz
        analysis = self._analyzer.analyze(sql, dialect="duckdb")
        if analysis.statement_type != "SELECT":
            raise ExecutionError("Stage-0 backend only executes SELECT")
        wrapped = f"SELECT * FROM ({sql.rstrip().rstrip(';')}) AS _agent3_eval LIMIT {limits.max_rows + 1}"
        try:
            cursor = self._conn.execute(wrapped)
            rows = cursor.fetchall()
        except Exception as exc:
            raise ExecutionError(str(exc)) from exc
        if len(rows) > limits.max_rows:
            raise ExecutionLimitExceeded(f"query returned more than service limit {limits.max_rows}; result was not silently truncated")
        columns = tuple(item[0] for item in cursor.description or ())
        return ResultSet(columns=columns, rows=tuple(tuple(row) for row in rows))
