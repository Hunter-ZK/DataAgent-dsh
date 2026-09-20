from __future__ import annotations

from pathlib import Path

import pytest

from agent3.contracts.authz import AuthzContext, DataScope
from agent3.execution.models import ExecutionLimits, ResultSet
from agent3.policy.compiler import PolicyRegistry, SQLPolicyCompiler
from agent3.policy.ir import PolicyIR, PolicyOperator, PolicyRule, PrincipalSelector
from agent3.query.interpreter import DeterministicQuestionInterpreter
from agent3.semantic.models import QueryIR
from agent3.services.factory import build_demo_core
from agent3.services.query_engine import QueryEngineService
from agent3_api.auth import LocalDevIdentityResolver, TrustedProxyIdentityResolver
from agent3_api.main import _identity_from_env
from agent3_api.persistence import POSTGRES_SCHEMA


class _FakeExecution:
    def __init__(self) -> None:
        self.sql = None

    def execute(self, authz, sql, *, limits: ExecutionLimits):
        self.sql = sql
        return ResultSet(("loan_balance",), ((123.0,),), elapsed_ms=1.2)


def test_trusted_proxy_identity_is_fail_closed() -> None:
    resolver = TrustedProxyIdentityResolver("secret")
    with pytest.raises(PermissionError):
        resolver.resolve({"x-principal": "alice"})
    authz = resolver.resolve({
        "x-auth-proxy-token": "secret",
        "x-principal": "alice",
        "x-roles": "analyst,pilot-region-user",
        "x-data-scopes": "region_code=4403|4401",
        "x-scope-version": "18",
    })
    assert authz.principal == "alice"
    assert authz.data_scopes[0].values == ("4403", "4401")
    assert authz.attributes["scope_version"] == "18"
    assert authz.attributes["auth_mode"] == "trusted-proxy"


def test_local_dev_identity_ignores_browser_asserted_headers() -> None:
    resolver = LocalDevIdentityResolver(
        principal="local-pilot",
        roles=("analyst",),
        data_scopes=(DataScope("region_code", ("4403",)),),
        scope_version="local-1",
    )
    authz = resolver.resolve({
        "x-principal": "mallory",
        "x-roles": "admin",
        "x-data-scopes": "region_code=9999",
    })
    assert authz.principal == "local-pilot"
    assert authz.roles == ("analyst",)
    assert authz.data_scopes[0].values == ("4403",)
    assert authz.attributes["auth_mode"] == "local-dev"


def test_dev_auth_composition_requires_loopback(monkeypatch) -> None:
    monkeypatch.setenv("AGENT3_DEV_AUTH", "1")
    monkeypatch.setenv("AGENT3_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="loopback"):
        _identity_from_env()


def test_production_identity_requires_proxy_secret(monkeypatch) -> None:
    monkeypatch.delenv("AGENT3_DEV_AUTH", raising=False)
    monkeypatch.delenv("AGENT3_PROXY_SHARED_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="AGENT3_PROXY_SHARED_SECRET"):
        _identity_from_env()


def test_dev_auth_composition_builds_host_owned_identity(monkeypatch) -> None:
    monkeypatch.setenv("AGENT3_DEV_AUTH", "1")
    monkeypatch.setenv("AGENT3_HOST", "127.0.0.1")
    monkeypatch.setenv("AGENT3_DEV_PRINCIPAL", "local-test")
    monkeypatch.setenv("AGENT3_DEV_DATA_SCOPES", "region_code=4403")
    resolver = _identity_from_env()
    authz = resolver.resolve({"x-principal": "browser-injected"})
    assert authz.principal == "local-test"
    assert authz.data_scopes[0].values == ("4403",)


def test_policy_compiler_intersects_identity_and_central_policy() -> None:
    registry = PolicyRegistry((PolicyIR(
        policy_id="region", version=2,
        selector=PrincipalSelector(roles=("analyst",)),
        rules=(PolicyRule("region_code", PolicyOperator.IN, ("4401", "4403")),),
    ),))
    compiler = SQLPolicyCompiler(registry)
    authz = AuthzContext("alice", roles=("analyst",), data_scopes=(DataScope("region_code", ("4403", "9999")),))
    applied = compiler.apply(authz, "SELECT balance_amt FROM dw.dwd_loan_snapshot", dialect="maxcompute")
    assert applied.effective_scopes[0].values == ("4403",)
    assert "region_code = '4403'" in applied.sql
    assert applied.policy_versions == ("region@2",)


def test_query_engine_applies_policy_and_executes_read_only_port() -> None:
    core = build_demo_core()
    backend = _FakeExecution()
    service = QueryEngineService(core=core, policy=SQLPolicyCompiler(), execution=backend)
    authz = AuthzContext("alice", data_scopes=(DataScope("region_code", ("4403",)),))
    result = service.run(authz, QueryIR(metric_id="loan_balance", time_values=("2026-08-31",)))
    assert result["execution_status"] == "completed"
    assert result["result"]["rows"] == [[123.0]]
    assert "region_code = '4403'" in result["sql"]
    assert backend.sql == result["sql"]


def test_interpreter_remains_server_owned_and_conservative() -> None:
    core = build_demo_core()
    interpreter = DeterministicQuestionInterpreter(core.semantics, core.metadata)
    authz = AuthzContext.system()
    outcome = interpreter.interpret(authz, "2026年8月31日深圳贷款余额是多少？")
    assert outcome.query_ir is not None
    assert outcome.task_contract.ir_valid is True
    clarification = interpreter.interpret(authz, "深圳贷款余额是多少？")
    assert clarification.task_contract.ir_valid is False


def test_postgres_schema_contains_canonical_replay_tables() -> None:
    for name in ("agent3_conversation", "agent3_message", "agent3_event", "agent3_clarification"):
        assert name in POSTGRES_SCHEMA
    assert "bigserial" in POSTGRES_SCHEMA.lower()
