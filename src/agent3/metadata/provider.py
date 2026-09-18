from __future__ import annotations

from typing import Protocol
from agent3.contracts.authz import AuthzContext
from agent3.metadata.models import TableMetadata


class MetadataProvider(Protocol):
    def search_tables(self, authz: AuthzContext, query: str, *, limit: int = 8) -> tuple[TableMetadata, ...]: ...
    def get_table(self, authz: AuthzContext, full_name: str) -> TableMetadata | None: ...
    def all_tables(self, authz: AuthzContext) -> tuple[TableMetadata, ...]: ...
