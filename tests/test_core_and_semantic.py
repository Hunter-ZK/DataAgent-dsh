import pytest

from agent3.contracts.authz import AuthzContext
from agent3.semantic.compiler import SemanticCompileError
from agent3.semantic.models import QueryIR
from agent3.services.factory import build_demo_core


def test_resolve_and_compile_standard_metric() -> None:
    core = build_demo_core()
    authz = AuthzContext.system()
    assert core.resolve_metric(authz, "余额")["resolved"] is True
    compiled = core.compile_query(authz, QueryIR(metric_id="loan_balance", dimensions=("org_id",), time_values=("2026-08-31",)))
    assert "SUM(balance_amt)" in compiled["sql"]
    assert "status <> 'cancelled'" in compiled["sql"]
    assert "dt = '2026-08-31'" in compiled["sql"]
    assert compiled["validation"]["valid"] is True


def test_non_additive_metric_rejects_multiple_snapshots() -> None:
    core = build_demo_core()
    with pytest.raises(SemanticCompileError):
        core.compile_query(AuthzContext.system(), QueryIR(metric_id="loan_balance", time_values=("2026-07-31", "2026-08-31")))


def test_schema_and_search_are_structured() -> None:
    core = build_demo_core()
    authz = AuthzContext.system()
    assert core.search_tables(authz, "贷款快照")["tables"][0]["full_name"] == "dw.dwd_loan_snapshot"
    schema = core.get_schema(authz, "dwd_loan_snapshot")
    assert schema["found"] is True
    assert {c["name"] for c in schema["columns"]} >= {"dt", "balance_amt", "region_code"}
