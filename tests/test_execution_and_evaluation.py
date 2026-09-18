import pytest

from agent3.contracts.authz import AuthzContext
from agent3.evaluation.adapters import DirectAdapter
from agent3.evaluation.models import EvalTask, RunResult
from agent3.evaluation.runner import EvaluationRunner
from agent3.execution.duckdb_backend import DuckDBExecutionBackend, ExecutionLimitExceeded
from agent3.execution.models import ExecutionLimits


def backend() -> DuckDBExecutionBackend:
    value = DuckDBExecutionBackend()
    value.connection.execute("create table loan(org_id varchar, balance_amt integer)")
    value.connection.execute("insert into loan values ('A', 10), ('A', 20), ('B', 7)")
    return value


def test_stage0_execution_backend_compares_result_sets_not_sql_text() -> None:
    task = EvalTask("t1", "A余额", "select sum(balance_amt) as x from loan where org_id='A'")
    adapter = DirectAdapter(lambda task: RunResult(task.id, "select 10 + 20 as x", trace={"metric_resolution": "loan_balance"}))
    result = EvaluationRunner(backend()).evaluate(AuthzContext.system(), adapter, (task,))[0]
    assert result.passed is True
    assert result.execution_match is True


def test_execution_limit_errors_instead_of_silent_truncation() -> None:
    with pytest.raises(ExecutionLimitExceeded):
        backend().execute(AuthzContext.system(), "select * from loan", limits=ExecutionLimits(max_rows=2))
