from __future__ import annotations

import json
import time
from dataclasses import asdict

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent3.contracts.authz import AuthzContext
from agent3_api.auth import IdentityResolver
from agent3_api.contracts import AgentEvent
from agent3_api.conversation_store import ConversationStore
from agent3_api.event_store import ConversationEventStore
from agent3_api.orchestrator import ConversationOrchestrator


class CreateConversationRequest(BaseModel):
    title: str | None = None


class MessageRequest(BaseModel):
    objective: str
    context_metric_id: str | None = None
    page_context: str | None = None


class ClarificationAnswerRequest(BaseModel):
    answer: str


def _sse(event: AgentEvent) -> str:
    payload = {"type": event.event_type.value, **event.payload}
    return f"id: {event.seq}\nevent: {event.event_type.value}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def create_platform_app(
    *,
    orchestrator: ConversationOrchestrator,
    conversations: ConversationStore,
    events: ConversationEventStore,
    identity: IdentityResolver,
    cors_origins: tuple[str, ...] = (),
) -> FastAPI:
    app = FastAPI(title="DataAgent Platform API", version="0.3.0")
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Last-Event-ID"],
        )

    def authz_dependency(request: Request) -> AuthzContext:
        try:
            return identity.resolve(request.headers)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": "0.3.0"}

    @app.get("/api/me")
    def me(authz: AuthzContext = Depends(authz_dependency)):
        return {
            "principal": authz.principal,
            "roles": list(authz.roles),
            "data_scopes": [asdict(scope) for scope in authz.data_scopes],
            "scope_version": authz.attributes.get("scope_version"),
        }

    @app.get("/api/conversations")
    def list_conversations(authz: AuthzContext = Depends(authz_dependency)):
        return [asdict(item) for item in conversations.list_for_principal(authz.principal)]

    @app.post("/api/conversations")
    def create_conversation(payload: CreateConversationRequest, authz: AuthzContext = Depends(authz_dependency)):
        return asdict(conversations.create(authz.principal, title=payload.title))

    @app.get("/api/conversations/{conversation_id}/messages")
    def list_messages(conversation_id: str, authz: AuthzContext = Depends(authz_dependency)):
        record = conversations.get(conversation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        if record.principal != authz.principal:
            raise HTTPException(status_code=403, detail="conversation owner mismatch")
        return [asdict(item) for item in conversations.messages(conversation_id)]

    @app.post("/api/conversations/{conversation_id}/messages")
    def post_message(
        conversation_id: str,
        payload: MessageRequest,
        background: BackgroundTasks,
        authz: AuthzContext = Depends(authz_dependency),
    ):
        try:
            dispatch = orchestrator.start_turn(
                authz,
                conversation_id=conversation_id,
                objective=payload.objective,
                context_metric_id=payload.context_metric_id,
                page_context=payload.page_context,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if dispatch.background is not None:
            background.add_task(dispatch.background)
        return dispatch.response

    @app.post("/api/clarifications/{clarification_id}/answer")
    def answer_clarification(
        clarification_id: str,
        payload: ClarificationAnswerRequest,
        background: BackgroundTasks,
        authz: AuthzContext = Depends(authz_dependency),
    ):
        try:
            dispatch = orchestrator.answer_clarification(authz, clarification_id=clarification_id, answer=payload.answer)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if dispatch.background is not None:
            background.add_task(dispatch.background)
        return dispatch.response

    @app.get("/api/conversations/{conversation_id}/events")
    def get_events(
        conversation_id: str,
        after: int = 0,
        authz: AuthzContext = Depends(authz_dependency),
    ):
        record = conversations.get(conversation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        if record.principal != authz.principal:
            raise HTTPException(status_code=403, detail="conversation owner mismatch")
        return [asdict(item) for item in events.after(conversation_id, after)]

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
            while idle_ticks < 720:
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
