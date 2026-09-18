from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MessageRoute(StrEnum):
    QUERY_ENGINE = "query_engine"
    DSH = "dsh"


class AgentEventType(StrEnum):
    THINKING = "thinking"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    SQL = "sql"
    RESULT_TABLE = "result_table"
    CAVEAT = "caveat"
    CLARIFICATION_NEEDED = "clarification_needed"
    SCOPE_NOTICE = "scope_notice"
    ERROR = "error"
    DONE = "done"


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """Program-built handoff context from canonical history into dsh.

    This is intentionally smaller than the full conversation history. It is a
    derived view and must pass the LLM egress policy before model exposure.
    """

    conversation_id: str
    user_objective: str
    confirmed_metrics: tuple[str, ...] = ()
    confirmed_dimensions: tuple[str, ...] = ()
    previous_results_summary: str | None = None
    caveats: tuple[str, ...] = ()
    authz_summary: str = "本会话数据范围已按权限限定"
    unresolved: tuple[str, ...] = ()
    page_context: str | None = None


@dataclass(frozen=True, slots=True)
class AgentEvent:
    event_type: AgentEventType
    conversation_id: str
    message_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int | None = None


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    id: str
    conversation_id: str
    role: str
    route: MessageRoute
    content: dict[str, Any]
    dsh_session_id: str | None = None
    sql_hash: str | None = None
