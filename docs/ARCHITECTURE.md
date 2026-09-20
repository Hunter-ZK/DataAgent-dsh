# Architecture baseline

## 1. Frozen system boundary

The dependency direction is:

```text
React / trusted proxy
        -> agent3-api
        -> dsh SDK adapter OR Query Engine
        -> Agent3 Core services
        -> domain modules and ports
```

`src/agent3` is the Data Intelligence Core. Outside `agent3/adapters`, it cannot import `agent3_api`, dsh, MCP or FastAPI. `agent3-api` is an application/platform layer and may depend on Core. CI enforces this direction.

DeepSeek Harness is replaceable runtime infrastructure. It does not own Metadata truth, Semantic truth, Policy truth, canonical conversation history, production credentials or final routing authority.

## 2. Canonical ownership

| Concern | Owner |
| --- | --- |
| Conversation/message/event history | `agent3-api` |
| Business HITL / clarification state | `agent3-api` |
| Task routing | Programmatic `TaskRouter` |
| Metadata | Agent3 Metadata provider |
| Metric/dimension definitions | Semantic Registry |
| Policy | Canonical Policy IR |
| SQL correctness | deterministic Core validation |
| Standard query SQL construction | Query Engine / Semantic Compiler |
| Exploratory agent loop | local dsh SDK |
| Model inference | DeepSeek Official API |
| Database credentials | controlled execution service/backend only |

A dsh session is a derived runtime view. It is never the system of record for conversation state.

## 3. Query capability line

### 3.1 Query Understanding

The public API accepts natural-language user intent, not client-asserted `query_ir`, `ir_valid` or semantic coverage.

```text
User question
  -> DeterministicQuestionInterpreter
  -> approved Semantic Registry + Metadata
  -> READY / NEED_CLARIFICATION / REFUSED / EXPLORATORY
```

The interpreter fails closed: it does not invent tables, columns, metrics or snapshot semantics.

### 3.2 Programmatic routing

```text
Grounded TaskContract
  -> TaskRouter
      -> QUERY_ENGINE
      -> AGENTIC_ANALYSIS
```

The model does not own the final route.

### 3.3 Standard query path

```text
QueryIR
 -> SemanticCompiler
 -> SQLPolicyCompiler
 -> SQLValidator
 -> optional read-only ExecutionBackend
 -> result + caveat + scope evidence
```

Standard questions therefore do not pay a dsh/model round trip when the query is fully grounded.

### 3.4 Exploratory path

```text
Canonical conversation context
 -> Context Builder
 -> LLM Egress Gate
 -> per-principal local dsh SDK runtime
 -> DeepSeek Official API
 -> Agent3 MCP tools
 -> stable DataAgent events
 -> canonical Event Store / SSE
```

The dsh query profile disables shell, filesystem-write, plugin-manager, generic web and other developer mutation surfaces.

## 4. Business HITL vs Tool Approval HITL

These are separate concepts.

**Business HITL** is current scope and handles missing/ambiguous business meaning, for example snapshot date or metric ambiguity. It is owned by `agent3-api` and resumes the original user objective after the user answers.

**Tool Approval HITL** applies to future warehouse-development/write tools. It is deferred with the future `dataagent-dev-sdk` profile and must not block the business-query pilot.

## 5. Conversation and event model

`agent3-api` stores separate user and assistant messages. Assistant messages carry `reply_to_message_id`. SSE events are stable DataAgent contracts, not raw dsh wire events.

Event storage uses a monotonic `seq`. Clients reconnect with `Last-Event-ID` and the API replays events after that sequence.

Current local development can use in-memory stores. Pilot/deployed environments can use the PostgreSQL implementation for:

- `agent3_conversation`;
- `agent3_message`;
- `agent3_event`;
- `agent3_clarification`.

## 6. Identity and Policy

Production identity is injected by a trusted SSO/reverse proxy. Browser/model input cannot declare principal, role or data scope.

For local acceptance only, an explicit `AGENT3_DEV_AUTH=1` mode uses a fixed local identity. Composition rejects that mode when the API host is not loopback.

Policy is represented as implementation-independent Policy IR and compiled into SQL predicates. Identity scopes and central policy scopes are intersected. Empty intersections fail closed.

The future Superset integration, if implemented, must compile from the same Policy IR rather than maintain a second independent RLS definition.

## 7. Execution ports

`ExecutionBackend` is a stable port, not a dsh tool.

Current implementations:

- DuckDB evaluation backend;
- PostgreSQL read-only backend for replica/query-database integration.

The production backend is additive; it does not replace the evaluation backend. The PostgreSQL backend starts a read-only transaction and enforces application limits, but the database account itself must also be read-only.

## 8. LLM egress

The current model is DeepSeek Official API, so the system is not an offline deployment. Outbound model traffic must pass an egress contract.

Denied-by-default categories include identity, authorization state, credentials and raw row-detail data. Aggregate/model-visible content requires an explicit safe classification. The current regex/text checks are a conservative pilot guard, not a substitute for organization-approved DLP.

## 9. Evaluation

Two evaluation layers coexist:

- **Stage-0**: backend-independent SQL/result-set evaluation;
- **P0-Q**: business-query capability evaluation covering route, metric/table/column grounding, semantic validity, execution accuracy, clarification, refusal, caveat, scope disclosure and real-LLM evidence for agentic cases.

Standard Query Engine cases do not require LLM participation; exploratory cases may.

## 10. Current / Target / Deferred

### Current delivery architecture

P0-Q + A + B + C + pilot React shell are implemented as code and pass CI.

### Target architecture

Organization SSO, real business Metadata/Semantic/Policy assets, canonical PostgreSQL storage, read-only replica/query database, approved DLP/egress policy and 5–20 user pilot.

### Deferred architecture

- Superset embedding;
- Tool Approval Bridge;
- `dataagent-dev-sdk`;
- warehouse-development UI;
- background agents/scheduling;
- full BI/data-quality platform features.

These deferred items are intentionally not part of the current pilot acceptance gate.
