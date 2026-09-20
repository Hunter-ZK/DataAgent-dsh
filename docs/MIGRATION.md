# Agent3.0 -> DataAgent-dsh migration

## Source baseline

Migration behavior is based on the release-hardened Agent3.0 branch:

- repository: `Hunter-ZK/Agent3.0`;
- branch: `v1-release-hardening-20260913`;
- commit: `3189fa29da312ba216afa474b9f92f6380363932`;
- prior regression status: 133 Python tests passed, including trusted SQL and PySpark simulation gates.

This repository intentionally started with clean public Git history. Private databases, Excel dictionaries, private benchmarks and historical credentials are not imported.

## Migration principle

The migration is not a mechanical copy. The frozen architectural change is:

```text
Old Agent3.0
  LangGraph / internal agent orchestration

DataAgent-dsh
  Programmatic Query Router
      -> deterministic Query Engine
      -> local DeepSeek Harness agent runtime
```

DeepSeek Harness owns the open agent loop only. Agent3 continues to own Data Intelligence truth and deterministic gates.

## Capability mapping

| Agent3.0 capability | DataAgent-dsh destination | Current state |
| --- | --- | --- |
| SQLGlot analysis | `agent3.sql.analysis` | migrated |
| Trusted SQL validation | `agent3.sql.validation` | migrated and retained as deterministic gate |
| Metadata contracts | `agent3.metadata` | migrated; YAML provider added for pilot assets |
| Semantic metric model | `agent3.semantic` | migrated and expanded with dimensions/value vocabulary |
| Text-to-SQL planning | `agent3.query` + `TaskRouter` | redesigned as conservative Query Understanding + programmatic routing |
| Standard Text-to-SQL | `QueryEngineService` | deterministic compile/policy/validate/execute line implemented |
| Open analysis | dsh Python SDK | moved to replaceable local runtime |
| LangGraph orchestration | none in Core | deliberately not migrated |
| SQL execution simulator | DuckDB `ExecutionBackend` | retained for evaluation |
| production/read query execution | PostgreSQL read-only `ExecutionBackend` | added as separate implementation |
| row authorization | Policy IR + SQL compiler | upgraded from narrow ad-hoc filter to canonical policy contract |
| conversation state | `agent3-api` | new canonical owner; dsh session is derived state |
| clarification HITL | `agent3-api` Business HITL | implemented independently of dsh Tool Approval |
| dsh Tool Approval | future development line | deferred until write-capable development tools exist |
| evaluation | Stage-0 + P0-Q | expanded to business-query gates |
| UI | React pilot shell | added |
| API | `agent3-api` | added REST/SSE platform boundary |
| identity | Trusted Proxy adapter | added; local loopback dev identity exists only for acceptance |
| platform persistence | PostgreSQL stores | added for conversation/message/event/clarification |
| LLM egress | DeepSeek Official + Egress Contract | added pilot boundary |

## Important semantic change

The new business-query line does not treat model-generated SQL as the primary product contract.

```text
Question
 -> approved Metric/Dimension/Metadata grounding
 -> QueryIR
 -> SemanticCompiler
 -> Policy IR
 -> SQLValidator
 -> optional read-only execution
```

Unknown or ambiguous business semantics produce clarification/refusal instead of model guessing.

## Runtime change

The current model deployment choice is:

```text
Local React / agent3-api / DeepSeek Harness SDK / MCP / Core
                         |
                         +-> DeepSeek Official API
```

No local LLM server is required for the current pilot. Old references to `LOCAL_LLM_KEY`, `127.0.0.1:8100` and `deepseek-v3-local` are retired from the platform path.

The Node dsh Web profile remains a debugging/integration asset. The platform product path uses the pinned Python SDK runtime and the restricted `dataagent-query-sdk` profile.

## Human-in-the-loop change

Two concepts are now separated:

- **Business HITL** — clarification of metric/time/dimension/business semantics; current pilot scope;
- **Tool Approval HITL** — approval for future write-capable/shell/DDL tools; deferred to the data-development line.

The query pilot does not require Tool Approval because the restricted query profile does not expose those mutation tools.

## Platform state after migration

The platform branch now includes:

- P0-Q evaluation;
- deterministic Query Understanding;
- Programmatic Task Router;
- Query Engine;
- Policy IR;
- read-only PostgreSQL execution port;
- `agent3-api` canonical conversation/event layer;
- dsh SDK runtime pool;
- DeepSeek Official API path;
- Business HITL;
- PostgreSQL persistence implementation;
- React pilot shell;
- Trusted Proxy identity adapter;
- loopback-only local acceptance identity;
- LLM egress pilot guard;
- Python/dsh/Guard/Web CI gates.

## Deliberately not migrated or not yet productized

- private historical metadata databases;
- private production SQL benchmark data;
- organization SSO/LDAP implementation;
- organization-approved DLP;
- real production Metadata/Semantic/Policy assets;
- production database credentials;
- Superset embedding;
- warehouse-development React UI;
- Tool Approval Bridge;
- background agents/schedulers.

These omissions are intentional scope decisions, not hidden V1 dependencies.
