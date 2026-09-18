from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from agent3.contracts.authz import AuthzContext


@dataclass(frozen=True, slots=True)
class VerifiedSQL:
    question: str
    sql_text: str
    tables: tuple[str, ...]
    metrics: tuple[str, ...]
    verified_by: str
    verified_at: str
    invalid_at: str | None = None
    hit_count: int = 0


class InMemoryVerifiedSQLStore:
    def __init__(self) -> None:
        self._items: list[VerifiedSQL] = []

    def register(self, authz: AuthzContext, *, question: str, sql_text: str, tables: tuple[str, ...], metrics: tuple[str, ...] = ()) -> VerifiedSQL:
        item = VerifiedSQL(question, sql_text, tables, metrics, authz.principal, datetime.now(timezone.utc).isoformat())
        self._items.append(item)
        return item

    def search(self, authz: AuthzContext, query: str, *, limit: int = 5) -> tuple[VerifiedSQL, ...]:
        _ = authz
        tokens = {token.casefold() for token in query.split() if token.strip()}
        scored: list[tuple[int, int, VerifiedSQL]] = []
        for index, item in enumerate(self._items):
            if item.invalid_at is not None:
                continue
            text = (item.question + " " + " ".join(item.tables) + " " + " ".join(item.metrics)).casefold()
            score = sum(token in text for token in tokens)
            if score:
                scored.append((score, -index, item))
        scored.sort(key=lambda row: (-row[0], row[1]))
        return tuple(row[2] for row in scored[:limit])
