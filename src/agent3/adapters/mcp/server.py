from __future__ import annotations

import os
from agent3.adapters.mcp.authz import static_authz_provider
from agent3.adapters.mcp.tools import MCPToolAdapter
from agent3.contracts.authz import AuthzContext
from agent3.services.factory import build_demo_core


def build_poc_server():
    """Build Stage-3 PoC server; production identity propagation must replace static identity."""
    if os.getenv("AGENT3_MCP_POC_MODE") != "1":
        raise RuntimeError("Static MCP identity is PoC-only. Set AGENT3_MCP_POC_MODE=1 for isolated PoC, or compose MCPToolAdapter with an authenticated AuthzProvider.")
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install dataagent-dsh[mcp] to run the MCP transport") from exc

    adapter = MCPToolAdapter(build_demo_core(), static_authz_provider(AuthzContext(principal="dsh-poc", roles=("poc",), purpose="stage3-poc")))
    mcp = FastMCP("agent3", host="127.0.0.1", port=8900)
    mcp.tool()(adapter.search_tables)
    mcp.tool()(adapter.get_schema)
    mcp.tool()(adapter.get_semantic_model)
    mcp.tool()(adapter.resolve_metric)
    mcp.tool()(adapter.search_verified_sql)
    mcp.tool()(adapter.validate_sql)
    mcp.tool()(adapter.explain_sql)
    mcp.tool()(adapter.compile_query)
    # Safe HITL acceptance surface: guard-plugin requires approval before this tool runs,
    # while Agent3 Core always reports execution_enabled=False in V1.
    mcp.tool()(adapter.submit_ddl)
    return mcp


def main() -> None:
    build_poc_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()
