from pathlib import Path
import yaml

from agent3.adapters.mcp.authz import static_authz_provider
from agent3.adapters.mcp.tools import MCPToolAdapter
from agent3.contracts.authz import AuthzContext
from agent3.services.factory import build_demo_core

ROOT = Path(__file__).resolve().parents[1]


def test_mcp_adapter_injects_principal_outside_model_arguments() -> None:
    adapter = MCPToolAdapter(build_demo_core(), static_authz_provider(AuthzContext(principal="session-u1")))
    assert adapter.get_schema("dwd_loan_snapshot")["found"] is True


def test_submit_ddl_is_exposed_for_hitl_but_never_executes_in_v1() -> None:
    adapter = MCPToolAdapter(build_demo_core(), static_authz_provider(AuthzContext(principal="session-u1")))
    result = adapter.submit_ddl("CREATE TABLE dw.acceptance_probe(id BIGINT)")
    assert result == {
        "accepted": False,
        "approval_required": True,
        "execution_enabled": False,
        "reason": "Production DDL execution is outside V1 and cannot be bypassed by an adapter.",
    }


def test_dsh_profile_disables_external_network_plugins() -> None:
    text = (ROOT / "dsh/profile/cordis.patch.yml").read_text(encoding="utf-8")
    for plugin_id in ("session-log-deepseek", "session-telemetry-otel", "web-search-deepseek", "web-fetch-http", "tool-web"):
        assert f"id: {plugin_id}" in text
    assert text.count("disabled: true") >= 5
    assert "failOnStartupError: true" in text
    assert "includeShippedRoot: false" in text
    yaml.safe_load(text)


def test_guard_plugin_contains_monotonic_guard_and_fail_closed_approval() -> None:
    text = (ROOT / "guard-plugin/src/index.ts").read_text(encoding="utf-8")
    assert "ctx.tools.guard" in text
    assert "tools/pre-execute" in text
    assert "tools/result" in text
    assert "outcome === 'allowed-once'" in text
    assert "approval failed closed" in text


def test_mcp_poc_server_registers_hitl_submit_ddl_tool() -> None:
    text = (ROOT / "src/agent3/adapters/mcp/server.py").read_text(encoding="utf-8")
    assert "mcp.tool()(adapter.submit_ddl)" in text
