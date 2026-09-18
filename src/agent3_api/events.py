from __future__ import annotations

from typing import Any

from agent3_api.contracts import AgentEvent, AgentEventType


def _event_payload(notification: Any) -> dict[str, Any]:
    payload = getattr(notification, "payload", None)
    return payload if isinstance(payload, dict) else {}


def translate_dsh_notification(
    notification: Any,
    *,
    conversation_id: str,
    message_id: str,
) -> AgentEvent | None:
    """Translate unstable dsh wire notifications into DataAgent-owned events.

    Unknown notifications are intentionally ignored instead of being forwarded
    raw to the frontend. This keeps dsh upgrades behind one compatibility seam.
    """

    method = getattr(notification, "method", None)
    payload = _event_payload(notification)

    if method == "session.status":
        if payload.get("status") == "idle":
            return AgentEvent(
                AgentEventType.DONE,
                conversation_id,
                message_id,
                {"finish_reason": "idle"},
            )
        return None

    if method != "session.event":
        return None

    wire_event = payload.get("event")
    if not isinstance(wire_event, dict):
        return None
    event_type = wire_event.get("type")
    data = wire_event.get("data")
    data = data if isinstance(data, dict) else {}

    if event_type == "assistant/message":
        message = data.get("message") if isinstance(data.get("message"), dict) else data
        content = message.get("content") if isinstance(message, dict) else None
        text_parts: list[str] = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(str(block.get("text") or ""))
        if text_parts:
            return AgentEvent(
                AgentEventType.THINKING,
                conversation_id,
                message_id,
                {"text": "".join(text_parts)},
            )
        return None

    if event_type in {"tool/start", "tool/call"}:
        tool = data.get("tool") or data.get("name") or "unknown"
        return AgentEvent(
            AgentEventType.TOOL_START,
            conversation_id,
            message_id,
            {"tool": str(tool)},
        )

    if event_type in {"tool/result", "tool/end"}:
        tool = data.get("tool") or data.get("name") or "unknown"
        ok = data.get("ok")
        return AgentEvent(
            AgentEventType.TOOL_RESULT,
            conversation_id,
            message_id,
            {"tool": str(tool), "ok": True if ok is None else bool(ok)},
        )

    if event_type == "turn/end":
        reason = data.get("reason") if isinstance(data.get("reason"), dict) else {}
        return AgentEvent(
            AgentEventType.DONE,
            conversation_id,
            message_id,
            {"finish_reason": reason.get("kind", "unknown")},
        )

    return None
