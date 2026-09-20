# DataAgent Pilot Acceptance

This document defines the gate after local acceptance and before a 5–20 user business pilot.

It is intentionally stricter than `LOCAL_ACCEPTANCE.md`: local acceptance proves the platform works on one developer machine; pilot acceptance proves the organization-specific identity, data, policy and egress boundaries are suitable for real users.

## 1. Entry criteria

Do not start the pilot until all are true:

- local acceptance is complete;
- Python/Core/SDK/dsh/Guard/Web CI is green;
- real DeepSeek Official + local dsh SDK + MCP smoke has passed;
- at least one P0-Q run exists against a real-business question set;
- approved Metadata/Semantic/Policy assets are available for the selected pilot domain.

## 2. Pilot architecture

```text
Business user
 -> organization SSO / trusted reverse proxy
 -> agent3-api
 -> canonical PostgreSQL conversation/event store
 -> Query Understanding
 -> Programmatic Router
      -> Query Engine -> read-only replica/query DB
      -> dsh SDK -> DeepSeek Official API -> Agent3 MCP
```

`AGENT3_DEV_AUTH` is forbidden in the pilot.

## 3. Identity gate

Required evidence:

- browser-supplied identity headers are stripped by the proxy;
- authenticated principal is injected by the trusted boundary;
- role/data scope/scope version are correct;
- invalid/missing proxy token is rejected;
- user A cannot read user B's conversation IDs/messages/events;
- permission changes invalidate or supersede stale scope versions according to the organization session/token design.

Target: **zero cross-user authorization failures**.

## 4. Data-policy gate

For at least two pilot users with different scopes:

- run the same business question;
- confirm Policy IR compiles different effective predicates;
- confirm result sets respect each scope;
- confirm empty identity/central-policy intersections deny rather than widen access;
- confirm unsupported multi-table policy propagation fails closed.

Target: **zero out-of-scope rows**.

## 5. Read-only execution gate

Verify independently of application code:

- database account cannot INSERT/UPDATE/DELETE/DDL;
- preferably points to a read replica or isolated query database;
- `READ ONLY` transaction is active;
- statement timeout works;
- row/result limits work;
- cancellation/timeout produces observable errors, not hanging turns;
- database credentials are not present in dsh environment/config/workspace.

## 6. LLM egress gate

Current model inference uses DeepSeek Official API.

Before real financial/business data is used, document and approve:

- allowed outbound endpoint(s);
- allowed content classes;
- forbidden PII/account/customer identifiers;
- whether SQL literals need masking;
- whether schema/table/field names may leave the network;
- aggregate-result minimum cohort/threshold rules;
- retention/logging expectations;
- organization DLP/control owner.

The repository's conservative text gate is not sufficient evidence for enterprise approval.

## 7. P0-Q business capability gate

Build a real-business benchmark of at least 30–50 questions.

Recommended mix:

- 10 simple metric questions;
- 10 time/region/dimension combinations;
- 5 ambiguous business definitions;
- 5 missing-context questions that should clarify;
- 5 unsupported questions that should refuse;
- 5–10 exploratory/why/diagnostic questions.

Measure:

- Route Accuracy;
- Metric Resolution;
- Table Grounding;
- Column Grounding;
- Semantic Validity;
- Execution Accuracy;
- Clarification Accuracy;
- Refusal Accuracy;
- Caveat correctness;
- Scope Disclosure;
- real-LLM evidence for agentic cases.

Thresholds should be frozen before pilot launch rather than adjusted after seeing the results.

## 8. dsh/LLM runtime gate

Using real DeepSeek credentials and representative exploratory prompts:

- dsh runtime starts/reuses correctly per principal;
- restricted query profile exposes no shell/fs/plugin-manager surfaces;
- Agent3 MCP is reachable;
- unknown dsh events do not leak raw protocol payloads to the frontend;
- runtime timeout/crash produces stable DataAgent error events;
- idle runtime reclamation works;
- no production database connectivity exists from dsh runtime.

## 9. Persistence and SSE gate

With `AGENT3_PLATFORM_POSTGRES_DSN`:

- conversations persist across API restart;
- user/assistant message IDs remain distinct;
- `reply_to_message_id` is correct;
- event `seq` is monotonic;
- `Last-Event-ID` replay resumes after disconnect;
- clarification requests survive reconnect/restart according to the persistence contract;
- concurrent users do not share sessions/events.

## 10. Operational gate

Minimum pilot observability:

- API health/readiness;
- dsh runtime start/failure counts;
- model request latency/error rate;
- Query Engine latency/error rate;
- database timeout/error rate;
- clarification/refusal rate;
- route distribution;
- redacted audit events without raw credentials or unauthorized row-detail output.

## 11. Pilot exit criteria

A 5–20 user pilot is considered technically ready when:

- security/identity/data gates have zero critical failures;
- the real P0-Q benchmark meets frozen thresholds;
- real DeepSeek + dsh + MCP path is stable under representative concurrency;
- standard-query path is correct without requiring the model;
- Business HITL/refusal behavior is understandable to pilot users;
- all known high-severity issues have an owner and disposition.

## 12. Explicitly deferred

The business-query pilot does not require:

- Superset;
- Tool Approval Bridge;
- write-capable DDL execution;
- warehouse-development UI;
- scheduled/background agents.

Do not add these to pilot scope unless the business-query pilot has already demonstrated a concrete need.
