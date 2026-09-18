from __future__ import annotations

import uuid
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class ClarificationRequest:
    id: str
    conversation_id: str
    message_id: str
    question: str
    options: tuple[str, ...] = ()
    unresolved_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClarificationAnswer:
    request_id: str
    answer: str


class ClarificationStore:
    """Stage-A in-memory Business HITL state; durable storage comes in Stage C."""

    def __init__(self) -> None:
        self._pending: dict[str, ClarificationRequest] = {}
        self._answers: dict[str, ClarificationAnswer] = {}
        self._lock = Lock()

    def create(
        self,
        *,
        conversation_id: str,
        message_id: str,
        question: str,
        options: tuple[str, ...] = (),
        unresolved_fields: tuple[str, ...] = (),
    ) -> ClarificationRequest:
        if not question.strip():
            raise ValueError("clarification question must not be empty")
        request = ClarificationRequest(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            message_id=message_id,
            question=question,
            options=options,
            unresolved_fields=unresolved_fields,
        )
        with self._lock:
            self._pending[request.id] = request
        return request

    def answer(self, request_id: str, answer: str) -> ClarificationAnswer:
        if not answer.strip():
            raise ValueError("clarification answer must not be empty")
        with self._lock:
            if request_id not in self._pending:
                raise KeyError(request_id)
            resolved = ClarificationAnswer(request_id=request_id, answer=answer)
            self._answers[request_id] = resolved
            self._pending.pop(request_id)
        return resolved

    def pending(self, request_id: str) -> ClarificationRequest | None:
        with self._lock:
            return self._pending.get(request_id)
