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
