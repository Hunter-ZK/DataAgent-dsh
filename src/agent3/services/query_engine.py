from __future__ import annotations

from dataclasses import asdict
from typing import Any

from agent3.contracts.authz import AuthzContext
from agent3.execution.backend import ExecutionBackend
from agent3.execution.models import ExecutionLimits
from agent3.policy.compiler import SQLPolicyCompiler
from agent3.semantic.models import QueryIR
from agent3.services.core import Agent3Core


class QueryEngineError(RuntimeError):
    pass


class QueryEngineService:
    """Deterministic standard-query path: compile -> policy -> validate -> execute."""

    def __init__(
        self,
        *,
        core: Agent3Core,
        policy: SQLPolicyCompiler | None = None,
        execution: ExecutionBackend | None = None,
        limits: ExecutionLimits | None = None,
    ) -> None:
        self._core = core
        self._policy = policy or SQLPolicyCompiler()
        self._execution = execution
        self._limits = limits or ExecutionLimits()

    def run(self, authz: AuthzContext, ir: QueryIR, *, dialect: str = "maxcompute") -> dict[str, Any]:
        compiled = self._core.compile_query(authz, ir)
        application = self._policy.apply(authz, compiled["sql"], dialect=dialect)
        validation = self._core.validate_sql(
            authz,
            application.sql,
            dialect=dialect,
            metric_id=ir.metric_id,
        )
        if not validation.get("valid", False):
            raise QueryEngineError("policy-adjusted SQL failed trusted validation")

        response: dict[str, Any] = {
            "sql": application.sql,
            "validation": validation,
            "policy": {
                "versions": list(application.policy_versions),
                "effective_scopes": [asdict(scope) for scope in application.effective_scopes],
            },
            "execution_status": "not_configured",
            "result": None,
        }
        if self._execution is not None:
            result = self._execution.execute(authz, application.sql, limits=self._limits)
            response["execution_status"] = "completed"
            response["result"] = {
                "columns": list(result.columns),
                "rows": [list(row) for row in result.rows],
                "row_count": result.row_count,
                "truncated": result.truncated,
                "elapsed_ms": result.elapsed_ms,
            }
        return response
