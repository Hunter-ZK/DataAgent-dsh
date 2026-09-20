# DataAgent Platform Pilot

## Runtime boundary

The pilot product path is:

```text
browser
 -> organization SSO / trusted reverse proxy
 -> agent3-api
 -> canonical PostgreSQL state
 -> Query Understanding
 -> Programmatic Router
      -> Query Engine -> read-only replica/query DB
      -> dsh Python SDK -> DeepSeek Official API -> Agent3 MCP
```

The proxy authenticates the user, strips any browser-supplied `X-Principal` / `X-Roles` / `X-Data-Scopes` headers, injects trusted identity values and adds `X-Auth-Proxy-Token`. `agent3-api` rejects the request when the proxy token or principal is missing.

`agent3-api` owns canonical conversation state and stable SSE events. dsh is a derived local runtime for exploratory turns only. Standard semantic queries stay on the deterministic Query Engine path and do not start dsh.

## Local acceptance is a different mode

`AGENT3_DEV_AUTH=1` exists only for a developer machine and is restricted to loopback. It must not be enabled in pilot/shared environments.

For developer acceptance use:

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
.\scripts\start_platform.ps1
```

See `docs/LOCAL_ACCEPTANCE.md`.

## Required pilot configuration

- `AGENT3_PROXY_SHARED_SECRET`: secret shared only by trusted proxy and API service;
- `AGENT3_METADATA_YAML`: approved physical metadata asset;
- `AGENT3_SEMANTIC_YAML`: approved metric/dimension semantic asset;
- `AGENT3_POLICY_YAML`: approved Policy IR asset;
- `AGENT3_PLATFORM_POSTGRES_DSN`: canonical conversation/event/HITL PostgreSQL database;
- `AGENT3_READ_REPLICA_DSN`: dedicated read-only role on a replica or isolated query database;
- `DEEPSEEK_API_KEY`: model credential for agentic dsh turns;
- `AGENT3_DSH_HOME_ROOT`: per-principal local dsh runtime home root;
- `AGENT3_DSH_WORKSPACE_ROOT`: per-principal local dsh workspace root.

Install:

```bash
python -m pip install -e '.[platform,postgres,mcp]'
```

The database user behind `AGENT3_READ_REPLICA_DSN` must be read-only even though the backend also starts a `READ ONLY` transaction.

## Identity headers

The trusted proxy may inject:

- `X-Principal: alice`
- `X-Roles: analyst,pilot-region-user`
- `X-Data-Scopes: region_code=4403|4401;org_id=001`
- `X-Scope-Version: 18`
- `X-Auth-Proxy-Token: <shared-secret>`

These values are host-side facts. The browser and model do not own them.

## Query path

```text
question
  -> DeterministicQuestionInterpreter
  -> Semantic/Metadata grounding
  -> Programmatic TaskRouter
      -> Query Engine
           -> Semantic compile
           -> Policy IR compile
           -> Trusted SQL validation
           -> read-only execution
      -> dsh
           -> filtered handoff context
           -> DeepSeek Official
           -> Agent3 MCP
```

Missing snapshot dates, ambiguous dimensions or unknown metrics become Business HITL/refusal rather than guessed SQL.

## Persistence and replay

When `AGENT3_PLATFORM_POSTGRES_DSN` is configured, the platform uses canonical tables for:

- conversation;
- message;
- event;
- clarification.

Event `seq` is monotonic and drives SSE `Last-Event-ID` replay. dsh session state is not the source of truth.

Without the DSN the service uses in-memory stores for local development only.

## Runtime isolation

The current pilot strategy uses one local dsh runtime/home per principal. This is an identity-binding and failure-containment strategy, not a security sandbox.

The restricted query profile disables shell, filesystem mutation, generic web and plugin-manager surfaces. Infrastructure still owns network isolation.

## Model egress

The current pilot uses DeepSeek Official API, therefore the environment is not fully offline.

Required deployment posture:

- default-deny outbound network policy;
- explicitly approved DeepSeek Official endpoint(s);
- generic web search/fetch disabled;
- identity/authz/credential content not model-visible;
- raw row-detail data denied by default;
- enterprise DLP/egress review completed before real sensitive data is used.

## Read-only query database

Recommended order:

1. dedicated read replica or isolated query database;
2. read-only database role;
3. application `READ ONLY` transaction;
4. statement timeout and result limits;
5. no database credential in dsh runtime or workspace.

## Operational signals

At minimum monitor:

- API health/readiness;
- route distribution (Query Engine vs dsh);
- Query Engine latency/errors;
- dsh runtime starts/failures;
- model latency/errors;
- database timeout/errors;
- clarification/refusal rates;
- SSE disconnect/replay behavior;
- redacted audit/security events.

## Pilot release gate

Repository CI validates code contracts without external secrets. A real pilot still has to prove:

- organization SSO header integration;
- real read-replica connectivity and read-only privileges;
- organization-approved DLP/egress classification;
- real DeepSeek API turns;
- Policy IR behavior for multiple user scopes;
- PostgreSQL persistence/replay;
- representative multi-user load/timeout behavior;
- P0-Q benchmark thresholds on real business questions.

See `docs/PILOT_ACCEPTANCE.md` for the complete gate.
