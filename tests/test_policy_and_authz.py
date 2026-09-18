import inspect
import pytest

from agent3.contracts.authz import AuthzContext, DataScope
from agent3.policy.row_filter import PolicyError, RowFilterPolicy
from agent3.services.core import Agent3Core
from agent3.services.factory import build_demo_core


def test_single_dimension_scope_is_ast_rewritten() -> None:
    authz = AuthzContext(principal="u1", data_scopes=(DataScope("region_code", ("440300",)),))
    rewritten, changed = RowFilterPolicy().apply(authz, "select balance_amt from dw.dwd_loan_snapshot")
    assert changed is True
    assert "region_code = '440300'" in rewritten


def test_v1_policy_refuses_multitable_scope_guessing() -> None:
    authz = AuthzContext(principal="u1", data_scopes=(DataScope("region_code", ("440300",)),))
    with pytest.raises(PolicyError):
        RowFilterPolicy().apply(authz, "select l.balance_amt from dw.dwd_loan_snapshot l join dw.dim_org o on l.org_id=o.org_id")


def test_all_public_core_methods_take_authz_first() -> None:
    for name, member in inspect.getmembers(Agent3Core, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        params = list(inspect.signature(member).parameters)
        assert params[:2] == ["self", "authz"], name


def test_write_knowledge_requires_human_approval() -> None:
    core = build_demo_core()
    authz = AuthzContext(principal="reviewer")
    with pytest.raises(PermissionError):
        core.register_verified_sql(authz, question="q", sql="select 1", tables=(), human_approved=False)
    assert core.register_verified_sql(authz, question="q", sql="select 1", tables=(), human_approved=True)["verified_by"] == "reviewer"


def test_submit_ddl_is_contract_only_in_v1() -> None:
    result = build_demo_core().submit_ddl(AuthzContext.system(), "create table t(a int)")
    assert result["approval_required"] is True
    assert result["execution_enabled"] is False
