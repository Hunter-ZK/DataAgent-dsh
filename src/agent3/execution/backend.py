from __future__ import annotations

from typing import Protocol
from agent3.contracts.authz import AuthzContext
from agent3.execution.models import ExecutionLimits, ResultSet


class ExecutionBackend(Protocol):
    """Internal execution port. Not an agent tool in V1."""
    def execute(self, authz: AuthzContext, sql: str, *, limits: ExecutionLimits) -> ResultSet: ...
