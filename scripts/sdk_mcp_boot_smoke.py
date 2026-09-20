from __future__ import annotations

import os
from pathlib import Path

from agent3_api.harness_runtime import HarnessRuntimeConfig, HarnessRuntimePool


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY must be present, even for the no-prompt SDK boot smoke")

    runtime_root = ROOT / ".runtime" / "sdk-mcp-smoke"
    pool = HarnessRuntimePool(
        HarnessRuntimeConfig(
            root=runtime_root / "homes",
            workspace_root=runtime_root / "workspaces",
            patch_file=ROOT / "dsh" / "sdk" / "query.patch.yml",
            initialize_timeout_seconds=45,
            request_timeout_seconds=30,
        )
    )
    try:
        handle = pool.get("ci-sdk-mcp-smoke")
        dsh_bin = getattr(handle.harness.config, "dsh_bin", None)
        if not dsh_bin:
            raise RuntimeError("platform SDK did not receive an explicit bundled dsh runtime path")
        print(f"SDK runtime: {dsh_bin}")
        print("SDK MCP boot smoke: OK")
    finally:
        pool.close()


if __name__ == "__main__":
    main()
