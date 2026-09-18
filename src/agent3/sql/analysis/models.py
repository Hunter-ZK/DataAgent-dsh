from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SQLColumnRef:
    table: str | None
    name: str


@dataclass(frozen=True, slots=True)
class SQLAnalysis:
    sql: str
    dialect: str
    statement_type: str
    tables: tuple[str, ...]
    columns: tuple[SQLColumnRef, ...]
    where_sql: str | None
    normalized_sql: str
