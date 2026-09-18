from __future__ import annotations

from dataclasses import replace
from threading import Lock
from typing import Protocol

from agent3_api.contracts import AgentEvent


class ConversationEventStore(Protocol):
    """Canonical durable-event port used by SSE replay."""

    def append(self, event: AgentEvent) -> AgentEvent: ...

    def after(self, conversation_id: str, seq: int = 0, *, limit: int = 500) -> tuple[AgentEvent, ...]: ...


class InMemoryConversationEventStore:
    """Stage-A implementation; PostgreSQL replaces this port in Stage C."""

    def __init__(self) -> None:
        self._events: list[AgentEvent] = []
        self._seq = 0
        self._lock = Lock()

    def append(self, event: AgentEvent) -> AgentEvent:
        with self._lock:
            self._seq += 1
            persisted = replace(event, seq=self._seq)
            self._events.append(persisted)
            return persisted

    def after(self, conversation_id: str, seq: int = 0, *, limit: int = 500) -> tuple[AgentEvent, ...]:
        if limit <= 0:
            return ()
        with self._lock:
            matches = [
                event
                for event in self._events
                if event.conversation_id == conversation_id and (event.seq or 0) > seq
            ]
        return tuple(matches[:limit])
