from __future__ import annotations

import re
from agent3.contracts.authz import AuthzContext
from agent3.metadata.models import TableMetadata

_TOKEN = re.compile(r"[a-zA-Z0-9_\u4e00-\u9fff]+")


class InMemoryMetadataProvider:
    """Deterministic public provider used by tests, demos and Stage-0 evaluation."""
    def __init__(self, tables: tuple[TableMetadata, ...]) -> None:
        self._tables = {t.full_name.casefold(): t for t in tables}

    def all_tables(self, authz: AuthzContext) -> tuple[TableMetadata, ...]:
        _ = authz
        return tuple(self._tables.values())

    def get_table(self, authz: AuthzContext, full_name: str) -> TableMetadata | None:
        _ = authz
        key = full_name.casefold()
        if key in self._tables:
            return self._tables[key]
        if "." not in key:
            matches = [t for k, t in self._tables.items() if k.rsplit(".", 1)[-1] == key]
            return matches[0] if len(matches) == 1 else None
        return None

    def search_tables(self, authz: AuthzContext, query: str, *, limit: int = 8) -> tuple[TableMetadata, ...]:
        _ = authz
        tokens = {x.casefold() for x in _TOKEN.findall(query)}
        scored: list[tuple[int, str, TableMetadata]] = []
        for table in self._tables.values():
            haystack = " ".join([table.full_name, table.description, *table.aliases]).casefold()
            score = sum(3 if token in table.full_name.casefold() else 1 for token in tokens if token in haystack)
            if score:
                scored.append((score, table.full_name, table))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return tuple(item[2] for item in scored[: max(1, limit)])
