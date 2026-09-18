from agent3.contracts.authz import AuthzContext
from agent3.evaluation.adapters import DirectAdapter
from agent3.evaluation.models import EvalTask, RunResult
from agent3.evaluation.runner import EvaluationRunner
from agent3.execution.duckdb_backend import DuckDBExecutionBackend


def main() -> None:
    backend = DuckDBExecutionBackend()
    backend.connection.execute("create table loan(org_id varchar, balance_amt integer)")
    backend.connection.execute("insert into loan values ('A', 10), ('A', 20), ('B', 7)")
    tasks = (EvalTask(id="sum-balance-a", question="A机构贷款余额是多少", golden_sql="select sum(balance_amt) as balance from loan where org_id='A'"),)
    direct = DirectAdapter(lambda task: RunResult(task_id=task.id, sql="select 10 + 20 as balance", trace={"schema_selection": "loan", "metric_resolution": "loan_balance"}))
    results = EvaluationRunner(backend).evaluate(AuthzContext.system(), direct, tasks)
    print({"passed": sum(item.passed for item in results), "total": len(results)})


if __name__ == "__main__": main()
