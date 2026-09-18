from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from typing import Callable

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent3.contracts.authz import AuthzContext
from agent3.routing.models import TaskContract, TaskType
from agent3.routing.router import TaskRouter
from agent3.semantic.models import MandatoryFilter, QueryIR
from agent3.services.core import Agent3Core
from agent3_api.clarification import ClarificationStore
from agent3_api.context_builder import render_context_for_model
from agent3_api.contracts import (
    AgentEvent,
    AgentEventType,
    ConversationContext,
    ConversationMessage,
    MessageRoute,
)
from agent3_api.conversation_store import ConversationStore
from agent3_api.event_store import ConversationEventStore
from agent3_api.events import translate_dsh_notification
from agent3_api.harness_runtime import HarnessRuntimePool


class CreateConversationRequest(BaseModel):
    title: str | None = None


class QueryFilterRequest(BaseModel):
    field: str
    op: str
    value: str


class QueryIRRequest(BaseModel):
    metric_id: str
    dimensions: list[str] = Field(default_factory=list)
    filters: list[QueryFilterRequest] = Field(default_factory=list)
    time_values: list[str] = Field(default_factory=list)

    def to_domain(self) -> QueryIR:
        return QueryIR(
            metric_id=self.metric_id,
            dimensions=tuple(self.dimensions),
            filters=tuple(MandatoryFilter(item.field, item.op, item.value) for item in self.filters),
            time_values=tuple(self.time_values),
        )


class MessageRequest(BaseModel):
    objective: str
    task_type: TaskType
    required_capabilities: list[str] = Field(default_factory=list)
    ir_valid: bool = False
    semantic_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    query_ir: QueryIRRequest | None = None
    unresolved_fields: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    clarification_options: list[str] = Field(default_factory=list)
    page_context: str | None = None


class ClarificationAnswerRequest(BaseModel):
    answer: str


def _sse(event: AgentEvent) -> str:
    payload = {"type": event.event_type.value, **event.payload}
    return f"id: {event.seq}\nevent: {event.event_type.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_platform_app(
    *,
    core: Agent3Core,
    conversations: ConversationStore,
    events: ConversationEventStore,
    clarifications: ClarificationStore,
    runtime_pool: HarnessRuntimePool,
    resolve_authz: Callable[[], AuthzContext],
    router: TaskRouter | None = None,
) -> FastAPI:
    """Create the Stage-A platform API.

    ``resolve_authz`` is deliberately injected. Stage B will bind it to the
    real SSO/token flow; this factory does not ship an insecure default identity.
    """

    task_router = router or TaskRouter()
    app = FastAPI(title="DataAgent Platform API", version="0.2.0")

    def authz_dependency() -> AuthzContext:
        try:
            return resolve_authz()
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.post("/api/conversations")
    def create_conversation(
        payload: CreateConversationRequest,
        authz: AuthzContext = Depends(authz_dependency),
    ):
        return asdict(conversations.create(authz.principal, title=payload.title))

    @app.get("/api/conversations/{conversation_id}/messages")
    def list_messages(
        conversation_id: str,
        authz: AuthzContext = Depends(authz_dependency),
    ):
        record = conversations.get(conversation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        if record.principal != authz.principal:
            raise HTTPException(status_code=403, detail="conversation owner mismatch")
        return [asdict(message) for message in conversations.messages(conversation_id)]

    @app.post("/api/conversations/{conversation_id}/messages")
    def post_message(
        conversation_id: str,
        payload: MessageRequest,
        background: BackgroundTasks,
        authz: AuthzContext = Depends(authz_dependency),
    ):
        record = conversations.get(conversation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        if record.principal != authz.principal:
            raise HTTPException(status_code=403, detail="conversation owner mismatch")

        message_id = str(uuid.uuid4())
        if payload.unresolved_fields:
            if not payload.clarification_question:
                raise HTTPException(status_code=422, detail="unresolved_fields require clarification_question")
            request = clarifications.create(
                conversation_id=conversation_id,
                message_id=message_id,
                question=payload.clarification_question,
                options=tuple(payload.clarification_options),
                unresolved_fields=tuple(payload.unresolved_fields),
            )
            persisted = events.append(
                AgentEvent(
                    AgentEventType.CLARIFICATION_NEEDED,
                    conversation_id,
                    message_id,
                    {
                        "clarification_id": request.id,
                        "question": request.question,
                        "options": list(request.options),
                        "unresolved_fields": list(request.unresolved_fields),
                    },
                )
            )
            return {"message_id": message_id, "status": "clarification_required", "event_seq": persisted.seq}

        contract = TaskContract(
            task_type=payload.task_type,
            objective=payload.objective,
            required_capabilities=tuple(payload.required_capabilities),
            ir_valid=payload.ir_valid,
            semantic_coverage=payload.semantic_coverage,
        )
        route = task_router.route(contract)

        if route.value == "query_engine":
            if payload.query_ir is None:
                raise HTTPException(status_code=422, detail="query_engine route requires query_ir")
            result = core.compile_query(authz, payload.query_ir.to_domain())
            conversations.append_message(
                ConversationMessage(
                    id=message_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    route=MessageRoute.QUERY_ENGINE,
                    content=result,
                )
            )
            events.append(AgentEvent(AgentEventType.SQL, conversation_id, message_id, {"text": result["sql"]}))
            events.append(AgentEvent(AgentEventType.DONE, conversation_id, message_id, {"finish_reason": "query_engine"}))
            return {"message_id": message_id, "route": route.value, "status": "completed"}

        session_id = f"conversation-{conversation_id}"
        context = ConversationContext(
            conversation_id=conversation_id,
            user_objective=payload.objective,
            page_context=payload.page_context,
        )
        prompt = render_context_for_model(context) + "\n\n[Current user request]\n" + payload.objective

        def run_agent() -> None:
            def on_notification(notification) -> None:
                translated = translate_dsh_notification(
                    notification,
                    conversation_id=conversation_id,
                    message_id=message_id,
                )
                if translated is not None:
                    events.append(translated)

            try:
                result = runtime_pool.run_turn(
                    principal=authz.principal,
                    session_id=session_id,
                    prompt=prompt,
                    on_notification=on_notification,
                )
                conversations.append_message(
                    ConversationMessage(
                        id=message_id,
                        conversation_id=conversation_id,
                        role="assistant",
                        route=MessageRoute.DSH,
                        dsh_session_id=session_id,
                        content={
                            "text": getattr(result, "final_response", ""),
                            "finish_reason": getattr(result, "finish_reason", None),
                        },
                    )
                )
            except Exception as exc:  # runtime failures must become observable events
                events.append(AgentEvent(AgentEventType.ERROR, conversation_id, message_id, {"message": str(exc)}))

        background.add_task(run_agent)
        return {"message_id": message_id, "route": route.value, "status": "accepted"}

    @app.post("/api/clarifications/{clarification_id}/answer")
    def answer_clarification(
        clarification_id: str,
        payload: ClarificationAnswerRequest,
        authz: AuthzContext = Depends(authz_dependency),
    ):
        pending = clarifications.pending(clarification_id)
        if pending is None:
            raise HTTPException(status_code=404, detail="clarification not found")
        record = conversations.get(pending.conversation_id)
        if record is None or record.principal != authz.principal:
            raise HTTPException(status_code=403, detail="clarification owner mismatch")
        return asdict(clarifications.answer(clarification_id, payload.answer))

    @app.get("/api/conversations/{conversation_id}/stream")
    def stream_events(
        conversation_id: str,
        last_event_id: int | None = Header(default=None, alias="Last-Event-ID"),
        authz: AuthzContext = Depends(authz_dependency),
    ):
        record = conversations.get(conversation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        if record.principal != authz.principal:
            raise HTTPException(status_code=403, detail="conversation owner mismatch")

        def generate():
            cursor = last_event_id or 0
            idle_ticks = 0
            while idle_ticks < 720:  # ~3 minutes at 250 ms; client may reconnect
                batch = events.after(conversation_id, cursor)
                if batch:
                    idle_ticks = 0
                    for event in batch:
                        cursor = event.seq or cursor
                        yield _sse(event)
                else:
                    idle_ticks += 1
                    if idle_ticks % 60 == 0:
                        yield ": keepalive\n\n"
                time.sleep(0.25)

        return StreamingResponse(generate(), media_type="text/event-stream")

    return app
