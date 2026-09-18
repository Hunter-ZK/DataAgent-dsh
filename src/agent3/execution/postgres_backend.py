from __future__ import annotations

import time

from agent3.contracts.authz import AuthzContext
from agent3.execution.models import ExecutionLimits, ResultSet


class PostgresReadOnlyBackend:
    """Read-only execution backend intended for a replica or dedicated query role.

    The driver is imported lazily so Core/tests do not require PostgreSQL. The
    database account must itself be read-only; the transaction-level guard is a
    second control, not the sole security boundary.
    """

    def __init__(self, dsn: str, *, application_name: str = "agent3-query") -> None:
        if not dsn.strip():
            raise ValueError("Postgres DSN must not be empty")
        self._dsn = dsn
        self._application_name = application_name

    def execute(self, authz: AuthzContext, sql: str, *, limits: ExecutionLimits) -> ResultSet:
        _ = authz
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - production extra only
            raise RuntimeError("install the postgres extra to use PostgresReadOnlyBackend") from exc

        started = time.monotonic()
        with psycopg.connect(
            self._dsn,
            autocommit=False,
            application_name=self._application_name,
            connect_timeout=max(1, min(30, int(limits.timeout_seconds))),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (f"{max(1, int(limits.timeout_seconds * 1000))}ms",),
                )
                cursor.execute(sql)
                description = cursor.description or ()
                columns = tuple(item.name for item in description)
                rows = list(cursor.fetchmany(limits.max_rows + 1)) if description else []
            connection.rollback()

        truncated = len(rows) > limits.max_rows
        visible = rows[: limits.max_rows]
        return ResultSet(
            columns=columns,
            rows=tuple(tuple(value for value in row) for row in visible),
            truncated=truncated,
            elapsed_ms=(time.monotonic() - started) * 1000,
        )
