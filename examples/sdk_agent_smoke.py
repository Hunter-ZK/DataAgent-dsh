from __future__ import annotations

import argparse
import os
from pathlib import Path

from agent3_api.events import translate_dsh_notification
from agent3_api.harness_runtime import HarnessRuntimeConfig, HarnessRuntimePool


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real DeepSeek Harness SDK + MCP smoke turn")
    parser.add_argument(
        "--prompt",
        default=(
            "必须调用 Agent3 MCP 的 search_tables 工具检索 loan 相关表，"
            "再简要说明你找到了什么。不要只凭模型记忆回答。"
        ),
    )
    parser.add_argument("--principal", default="local-acceptance")
    parser.add_argument("--session-id", default="sdk-smoke-001")
    args = parser.parse_args()

    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is required for the real-LLM SDK smoke")

    root = Path.cwd()
    config = HarnessRuntimeConfig(
        root=root / ".runtime" / "dsh-homes",
        workspace_root=root / ".runtime" / "workspaces",
        patch_file=root / "dsh" / "sdk" / "query.patch.yml",
    )
    pool = HarnessRuntimePool(config)

    def on_notification(notification) -> None:
        event = translate_dsh_notification(
            notification,
            conversation_id="local-smoke",
            message_id="local-smoke-message",
        )
        if event is not None:
            print(f"[{event.event_type.value}] {event.payload}")

    try:
        result = pool.run_turn(
            principal=args.principal,
            session_id=args.session_id,
            prompt=args.prompt,
            on_notification=on_notification,
        )
        print("\n=== FINAL RESPONSE ===")
        print(result.final_response)
        print(f"finish_reason={result.finish_reason}")
        return 0 if result.finish_reason != "error" else 2
    finally:
        pool.close()


if __name__ == "__main__":
    raise SystemExit(main())
