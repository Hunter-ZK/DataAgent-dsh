from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import Any

from agent3_api.clarification import ClarificationAnswer, ClarificationRequest
from agent3_api.contracts import AgentEvent, AgentEventType, ConversationMessage, MessageRoute
from agent3_api.conversation_store import ConversationRecord


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent3_conversation (
    id text PRIMARY KEY,
    principal text NOT NULL,
    title text NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent3_conversation_principal
    ON agent3_conversation(principal, created_at DESC);

CREATE TABLE IF NOT EXISTS agent3_message (
    id text PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES agent3_conversation(id) ON DELETE CASCADE,
    role text NOT NULL,
    route text NOT NULL,
    content jsonb NOT NULL,
    reply_to_message_id text NULL,
    dsh_session_id text NULL,
    sql_hash text NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent3_message_conversation
    ON agent3_message(conversation_id, created_at, id);

CREATE TABLE IF NOT EXISTS agent3_event (
    seq bigserial PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES agent3_conversation(id) ON DELETE CASCADE,
    message_id text NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent3_event_replay
    ON agent3_event(conversation_id, seq);

CREATE TABLE IF NOT EXISTS agent3_clarification (
    id text PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES agent3_conversation(id) ON DELETE CASCADE,
    message_id text NOT NULL,
    question text NOT NULL,
    original_objective text NOT NULL,
    context_metric_id text NULL,
    page_context text NULL,
    options jsonb NOT NULL,
    unresolved_fields jsonb NOT NULL,
    answer text NULL,
    answered_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
"""


class PostgresPlatformPersistence:
    """Stage-C durable canonical state. psycopg is imported only when configured."""

    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("platform Postgres DSN must not be empty")
        self._dsn = dsn
        self.conversations = _PostgresConversationStore(self)
        self.events = _PostgresEventStore(self)
        self.clarifications = _PostgresClarificationStore(self)

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - production extra only
            raise RuntimeError("install the postgres extra to use durable platform persistence") from exc
        return psycopg.connect(self._dsn)

    def initialize(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(POSTGRES_SCHEMA)


class _PostgresConversationStore:
    def __init__(self, db: PostgresPlatformPersistence) -> None:
        self._db = db

    def create(self, principal: str, *, title: str | None = None) -> ConversationRecord:
        record = ConversationRecord(str(uuid.uuid4()), principal, title)
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO agent3_conversation(id, principal, title) VALUES (%s, %s, %s)",
                    (record.id, record.principal, record.title),
                )
        return record

    def get(self, conversation_id: str) -> ConversationRecord | None:
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, principal, title FROM agent3_conversation WHERE id = %s",
                    (conversation_id,),
                )
                row = cursor.fetchone()
        return ConversationRecord(*row) if row else None

    def list_for_principal(self, principal: str, *, limit: int = 100) -> tuple[ConversationRecord, ...]:
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, principal, title FROM agent3_conversation WHERE principal = %s ORDER BY created_at DESC LIMIT %s",
                    (principal, limit),
                )
                rows = cursor.fetchall()
        return tuple(ConversationRecord(*row) for row in rows)

    def append_message(self, message: ConversationMessage) -> None:
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO agent3_message
                    (id, conversation_id, role, route, content, reply_to_message_id, dsh_session_id, sql_hash)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)""",
                    (
                        message.id,
                        message.conversation_id,
                        message.role,
                        message.route.value,
                        json.dumps(message.content, ensure_ascii=False, default=str),
                        message.reply_to_message_id,
                        message.dsh_session_id,
                        message.sql_hash,
                    ),
                )

    def messages(self, conversation_id: str) -> tuple[ConversationMessage, ...]:
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT id, conversation_id, role, route, content,
                    reply_to_message_id, dsh_session_id, sql_hash
                    FROM agent3_message WHERE conversation_id = %s ORDER BY created_at, id""",
                    (conversation_id,),
                )
                rows = cursor.fetchall()
        return tuple(
            ConversationMessage(
                id=row[0], conversation_id=row[1], role=row[2], route=MessageRoute(row[3]),
                content=row[4] if isinstance(row[4], dict) else json.loads(row[4]),
                reply_to_message_id=row[5], dsh_session_id=row[6], sql_hash=row[7],
            )
            for row in rows
        )


class _PostgresEventStore:
    def __init__(self, db: PostgresPlatformPersistence) -> None:
        self._db = db

    def append(self, event: AgentEvent) -> AgentEvent:
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO agent3_event(conversation_id, message_id, event_type, payload)
                    VALUES (%s, %s, %s, %s::jsonb) RETURNING seq""",
                    (
                        event.conversation_id,
                        event.message_id,
                        event.event_type.value,
                        json.dumps(event.payload, ensure_ascii=False, default=str),
                    ),
                )
                seq = int(cursor.fetchone()[0])
        return replace(event, seq=seq)

    def after(self, conversation_id: str, seq: int = 0, *, limit: int = 500) -> tuple[AgentEvent, ...]:
        if limit <= 0:
            return ()
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT seq, message_id, event_type, payload FROM agent3_event
                    WHERE conversation_id = %s AND seq > %s ORDER BY seq LIMIT %s""",
                    (conversation_id, seq, limit),
                )
                rows = cursor.fetchall()
        return tuple(
            AgentEvent(
                AgentEventType(row[2]), conversation_id, row[1],
                row[3] if isinstance(row[3], dict) else json.loads(row[3]), seq=int(row[0]),
            )
            for row in rows
        )


class _PostgresClarificationStore:
    def __init__(self, db: PostgresPlatformPersistence) -> None:
        self._db = db

    def create(
        self,
        *,
        conversation_id: str,
        message_id: str,
        question: str,
        original_objective: str,
        context_metric_id: str | None = None,
        page_context: str | None = None,
        options: tuple[str, ...] = (),
        unresolved_fields: tuple[str, ...] = (),
    ) -> ClarificationRequest:
        request = ClarificationRequest(
            id=str(uuid.uuid4()), conversation_id=conversation_id, message_id=message_id,
            question=question, original_objective=original_objective,
            context_metric_id=context_metric_id, page_context=page_context,
            options=options, unresolved_fields=unresolved_fields,
        )
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO agent3_clarification
                    (id, conversation_id, message_id, question, original_objective,
                     context_metric_id, page_context, options, unresolved_fields)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)""",
                    (
                        request.id, request.conversation_id, request.message_id, request.question,
                        request.original_objective, request.context_metric_id, request.page_context,
                        json.dumps(request.options, ensure_ascii=False),
                        json.dumps(request.unresolved_fields, ensure_ascii=False),
                    ),
                )
        return request

    def pending(self, request_id: str) -> ClarificationRequest | None:
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT id, conversation_id, message_id, question, original_objective,
                    context_metric_id, page_context, options, unresolved_fields
                    FROM agent3_clarification WHERE id = %s AND answer IS NULL""",
                    (request_id,),
                )
                row = cursor.fetchone()
        if not row:
            return None
        return ClarificationRequest(
            id=row[0], conversation_id=row[1], message_id=row[2], question=row[3],
            original_objective=row[4], context_metric_id=row[5], page_context=row[6],
            options=tuple(row[7] if isinstance(row[7], list) else json.loads(row[7])),
            unresolved_fields=tuple(row[8] if isinstance(row[8], list) else json.loads(row[8])),
        )

    def answer(self, request_id: str, answer: str) -> ClarificationAnswer:
        if not answer.strip():
            raise ValueError("clarification answer must not be empty")
        with self._db._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE agent3_clarification SET answer = %s, answered_at = now()
                    WHERE id = %s AND answer IS NULL RETURNING id""",
                    (answer.strip(), request_id),
                )
                row = cursor.fetchone()
        if row is None:
            raise KeyError(request_id)
        return ClarificationAnswer(request_id=request_id, answer=answer.strip())
