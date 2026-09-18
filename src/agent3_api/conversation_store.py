from __future__ import annotations

import uuid
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from agent3_api.contracts import ConversationMessage


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    id: str
    principal: str
    title: str | None = None


class ConversationStore(Protocol):
    def create(self, principal: str, *, title: str | None = None) -> ConversationRecord: ...
    def get(self, conversation_id: str) -> ConversationRecord | None: ...
    def list_for_principal(self, principal: str, *, limit: int = 100) -> tuple[ConversationRecord, ...]: ...
    def append_message(self, message: ConversationMessage) -> None: ...
    def messages(self, conversation_id: str) -> tuple[ConversationMessage, ...]: ...


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationRecord] = {}
        self._messages: list[ConversationMessage] = []
        self._lock = Lock()

    def create(self, principal: str, *, title: str | None = None) -> ConversationRecord:
        record = ConversationRecord(id=str(uuid.uuid4()), principal=principal, title=title)
        with self._lock:
            self._conversations[record.id] = record
        return record

    def get(self, conversation_id: str) -> ConversationRecord | None:
        with self._lock:
            return self._conversations.get(conversation_id)

    def list_for_principal(self, principal: str, *, limit: int = 100) -> tuple[ConversationRecord, ...]:
        with self._lock:
            matches = [item for item in self._conversations.values() if item.principal == principal]
        return tuple(reversed(matches[-max(0, limit):]))

    def append_message(self, message: ConversationMessage) -> None:
        with self._lock:
            if message.conversation_id not in self._conversations:
                raise KeyError(f"conversation does not exist: {message.conversation_id}")
            self._messages.append(message)

    def messages(self, conversation_id: str) -> tuple[ConversationMessage, ...]:
        with self._lock:
            return tuple(item for item in self._messages if item.conversation_id == conversation_id)
