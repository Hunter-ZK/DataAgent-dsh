from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Callable

from agent3.contracts.authz import AuthzContext
from agent3.query.interpreter import DeterministicQuestionInterpreter
from agent3.query.models import GroundedQuery, QueryClarification, QueryRefusal
from agent3.routing.models import Route
from agent3.routing.router import TaskRouter
from agent3.services.core import Agent3Core
from agent3.services.query_engine import QueryEngineService
from agent3_api.clarification import ClarificationStore
from agent3_api.context_builder import render_context_for_model
from agent3_api.contracts import AgentEvent, AgentEventType, ConversationContext, ConversationMessage, MessageRoute
from agent3_api.conversation_store import ConversationStore
from agent3_api.egress import TextEgressGate
from agent3_api.event_store import ConversationEventStore
from agent3_api.events import translate_dsh_notification
from agent3_api.harness_runtime import HarnessRuntimePool


@dataclass(slots=True)
class TurnDispatch:
    response: dict
    background: Callable[[], None] | None = None


class ConversationOrchestrator:
    """Canonical conversation owner and deterministic route dispatcher."""

    def __init__(
        self,
        *,
        core: Agent3Core,
        interpreter: DeterministicQuestionInterpreter,
        conversations: ConversationStore,
        events: ConversationEventStore,
        clarifications: ClarificationStore,
        runtime_pool: HarnessRuntimePool,
        egress_gate: TextEgressGate,
        query_engine: QueryEngineService | None = None,
        router: TaskRouter | None = None,
    ) -> None:
        self.core = core
        self.interpreter = interpreter
        self.conversations = conversations
        self.events = events
        self.clarifications = clarifications
        self.runtime_pool = runtime_pool
        self.egress_gate = egress_gate
        self.query_engine = query_engine
        self.router = router or TaskRouter()

    def start_turn(
        self,
        authz: AuthzContext,
        *,
        conversation_id: str,
        objective: str,
        context_metric_id: str | None = None,
        page_context: str | None = None,
        display_text: str | None = None,
    ) -> TurnDispatch:
        self._owned_conversation(authz, conversation_id)
        outcome = self.interpreter.interpret(authz, objective, context_metric_id=context_metric_id)
        if isinstance(outcome, QueryClarification):
            return self._clarify(conversation_id, objective, outcome, context_metric_id, page_context, display_text)
        if isinstance(outcome, QueryRefusal):
            return self._refuse(conversation_id, objective, outcome, display_text)
        return self._dispatch_grounded(authz, conversation_id, outcome, display_text or objective, page_context)

    def answer_clarification(self, authz: AuthzContext, *, clarification_id: str, answer: str) -> TurnDispatch:
        pending = self.clarifications.pending(clarification_id)
        if pending is None:
            raise KeyError("clarification not found")
        self._owned_conversation(authz, pending.conversation_id)
        self.clarifications.answer(clarification_id, answer)
        resumed = pending.original_objective + "\n用户补充：" + answer.strip()
        return self.start_turn(
            authz,
            conversation_id=pending.conversation_id,
            objective=resumed,
            context_metric_id=pending.context_metric_id,
            page_context=pending.page_context,
            display_text=answer.strip(),
        )

    def _clarify(self, conversation_id, objective, outcome, context_metric_id, page_context, display_text) -> TurnDispatch:
        message_id = str(uuid.uuid4())
        self.conversations.append_message(ConversationMessage(
            id=message_id, conversation_id=conversation_id, role="user", route=MessageRoute.PENDING,
            content={"text": display_text or objective},
        ))
        request = self.clarifications.create(
            conversation_id=conversation_id, message_id=message_id, question=outcome.question,
            original_objective=objective, context_metric_id=context_metric_id, page_context=page_context,
            unresolved_fields=outcome.missing_context,
        )
        event = self.events.append(AgentEvent(
            AgentEventType.CLARIFICATION_NEEDED, conversation_id, message_id,
            {"clarification_id": request.id, "question": request.question,
             "options": list(request.options), "unresolved_fields": list(request.unresolved_fields),
             "reason": outcome.reason},
        ))
        return TurnDispatch({"message_id": message_id, "status": "clarification_required", "clarification_id": request.id, "event_seq": event.seq})

    def _refuse(self, conversation_id, objective, outcome, display_text) -> TurnDispatch:
        user_id, assistant_id = str(uuid.uuid4()), str(uuid.uuid4())
        self.conversations.append_message(ConversationMessage(
            id=user_id, conversation_id=conversation_id, role="user", route=MessageRoute.REFUSED,
            content={"text": display_text or objective},
        ))
        self.conversations.append_message(ConversationMessage(
            id=assistant_id, conversation_id=conversation_id, role="assistant", route=MessageRoute.REFUSED,
            reply_to_message_id=user_id, content={"reason": outcome.reason, "evidence": asdict(outcome.evidence)},
        ))
        self.events.append(AgentEvent(AgentEventType.REFUSAL, conversation_id, assistant_id, {"reason": outcome.reason}))
        self.events.append(AgentEvent(AgentEventType.DONE, conversation_id, assistant_id, {"finish_reason": "refused"}))
        return TurnDispatch({"message_id": user_id, "response_message_id": assistant_id, "status": "refused", "reason": outcome.reason})

    def _dispatch_grounded(self, authz: AuthzContext, conversation_id: str, outcome: GroundedQuery, display_text: str, page_context: str | None) -> TurnDispatch:
        route = self.router.route(outcome.task_contract)
        user_id, assistant_id = str(uuid.uuid4()), str(uuid.uuid4())
        message_route = MessageRoute.QUERY_ENGINE if route is Route.QUERY_ENGINE else MessageRoute.DSH
        self.conversations.append_message(ConversationMessage(
            id=user_id, conversation_id=conversation_id, role="user", route=message_route, content={"text": display_text},
        ))

        if route is Route.QUERY_ENGINE:
            if outcome.query_ir is None:
                raise RuntimeError("Query Engine route requires a grounded QueryIR")
            result = self.query_engine.run(authz, outcome.query_ir) if self.query_engine else self.core.compile_query(authz, outcome.query_ir)
            content = {**result, "grounding": asdict(outcome.evidence)}
            self.conversations.append_message(ConversationMessage(
                id=assistant_id, conversation_id=conversation_id, role="assistant", route=MessageRoute.QUERY_ENGINE,
                reply_to_message_id=user_id, content=content,
            ))
            if outcome.evidence.caveats:
                self.events.append(AgentEvent(AgentEventType.CAVEAT, conversation_id, assistant_id, {"items": list(outcome.evidence.caveats)}))
            policy = result.get("policy") if isinstance(result, dict) else None
            if authz.data_scopes or (isinstance(policy, dict) and policy.get("effective_scopes")):
                self.events.append(AgentEvent(AgentEventType.SCOPE_NOTICE, conversation_id, assistant_id, {"text": "本次查询结果已按你的数据权限范围限定"}))
            self.events.append(AgentEvent(AgentEventType.SQL, conversation_id, assistant_id, {"text": result["sql"], "metric_id": outcome.evidence.metric_id}))
            result_table = result.get("result") if isinstance(result, dict) else None
            if result_table is not None:
                self.events.append(AgentEvent(AgentEventType.RESULT_TABLE, conversation_id, assistant_id, result_table))
            self.events.append(AgentEvent(AgentEventType.DONE, conversation_id, assistant_id, {"finish_reason": "query_engine"}))
            return TurnDispatch({"message_id": user_id, "response_message_id": assistant_id, "route": route.value, "status": "completed", "execution_status": result.get("execution_status")})

        context = ConversationContext(
            conversation_id=conversation_id,
            user_objective=outcome.task_contract.objective,
            confirmed_metrics=(outcome.evidence.metric_id,) if outcome.evidence.metric_id else (),
            confirmed_dimensions=outcome.query_ir.dimensions if outcome.query_ir else (),
            caveats=outcome.evidence.caveats,
            page_context=page_context,
        )
        prompt = render_context_for_model(context) + "\n\n[Current user request]\n" + outcome.task_contract.objective
        decision = self.egress_gate.evaluate(prompt, purpose="agentic_query")
        if not decision.allowed:
            self.conversations.append_message(ConversationMessage(
                id=assistant_id, conversation_id=conversation_id, role="assistant", route=MessageRoute.REFUSED,
                reply_to_message_id=user_id, content={"reason": decision.reason},
            ))
            self.events.append(AgentEvent(AgentEventType.REFUSAL, conversation_id, assistant_id, {"reason": decision.reason, "kind": "llm_egress"}))
            self.events.append(AgentEvent(AgentEventType.DONE, conversation_id, assistant_id, {"finish_reason": "refused"}))
            return TurnDispatch({"message_id": user_id, "response_message_id": assistant_id, "route": route.value, "status": "refused", "reason": decision.reason})

        session_id = f"conversation-{conversation_id}"
        def run_agent() -> None:
            def on_notification(notification) -> None:
                event = translate_dsh_notification(notification, conversation_id=conversation_id, message_id=assistant_id)
                if event is not None:
                    self.events.append(event)
            try:
                result = self.runtime_pool.run_turn(principal=authz.principal, session_id=session_id, prompt=prompt, on_notification=on_notification)
                self.conversations.append_message(ConversationMessage(
                    id=assistant_id, conversation_id=conversation_id, role="assistant", route=MessageRoute.DSH,
                    reply_to_message_id=user_id, dsh_session_id=session_id,
                    content={"text": getattr(result, "final_response", ""), "finish_reason": getattr(result, "finish_reason", None), "grounding": asdict(outcome.evidence)},
                ))
            except Exception as exc:
                self.events.append(AgentEvent(AgentEventType.ERROR, conversation_id, assistant_id, {"message": str(exc)}))
                self.events.append(AgentEvent(AgentEventType.DONE, conversation_id, assistant_id, {"finish_reason": "error"}))

        return TurnDispatch({"message_id": user_id, "response_message_id": assistant_id, "route": route.value, "status": "accepted"}, background=run_agent)

    def _owned_conversation(self, authz: AuthzContext, conversation_id: str):
        record = self.conversations.get(conversation_id)
        if record is None:
            raise KeyError("conversation not found")
        if record.principal != authz.principal:
            raise PermissionError("conversation owner mismatch")
        return record
