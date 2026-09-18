from __future__ import annotations

from agent3.contracts.authz import AuthzContext
from agent3.evaluation.adapters import EvaluationAdapter
from agent3.evaluation.models import EvalCaseResult, EvalTask
from agent3.execution.backend import ExecutionBackend
from agent3.execution.models import ExecutionLimits, ResultSet


def _canonical(result: ResultSet) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    rows = tuple(sorted(tuple(repr(cell) for cell in row) for row in result.rows))
    return result.columns, rows


class EvaluationRunner:
    def __init__(self, backend: ExecutionBackend, *, limits: ExecutionLimits | None = None) -> None:
        self._backend = backend
        self._limits = limits or ExecutionLimits(max_rows=10_000)

    def evaluate(self, authz: AuthzContext, adapter: EvaluationAdapter, tasks: tuple[EvalTask, ...]) -> tuple[EvalCaseResult, ...]:
        results: list[EvalCaseResult] = []
        for task in tasks:
            candidate = adapter.run(task)
            if candidate.error or not candidate.sql:
                results.append(EvalCaseResult(task.id, False, candidate.sql, False, candidate.error or "adapter returned no SQL", candidate.trace))
                continue
            try:
                golden = self._backend.execute(authz, task.golden_sql, limits=self._limits)
                actual = self._backend.execute(authz, candidate.sql, limits=self._limits)
                matched = _canonical(golden) == _canonical(actual)
                results.append(EvalCaseResult(task.id, matched, candidate.sql, matched, None if matched else "result set mismatch", candidate.trace))
            except Exception as exc:
                results.append(EvalCaseResult(task.id, False, candidate.sql, False, str(exc), candidate.trace))
        return tuple(results)
