# DataAgent Platform Pilot

## Runtime boundary

The production pilot is `browser -> trusted SSO/reverse proxy -> agent3-api`. The proxy authenticates the user, strips any browser-supplied `X-Principal`/`X-Roles`/`X-Data-Scopes` headers, injects trusted identity headers, and adds `X-Auth-Proxy-Token`. `agent3-api` rejects the request when the proxy token or principal is missing.

`agent3-api` owns canonical conversation state and stable SSE events. dsh is a derived local runtime for exploratory turns only. Standard semantic queries stay on the deterministic Query Engine path and do not start dsh.

## Required production configuration

- `AGENT3_PROXY_SHARED_SECRET`: shared only by the trusted proxy and API service.
- `AGENT3_METADATA_YAML`: approved physical metadata asset.
- `AGENT3_SEMANTIC_YAML`: approved metric/dimension semantic asset.
- `AGENT3_POLICY_YAML`: central Policy IR asset.
- `AGENT3_PLATFORM_POSTGRES_DSN`: canonical conversation/event/HITL PostgreSQL database.
- `AGENT3_READ_REPLICA_DSN`: dedicated read-only query role on a replica or isolated query database.
- `DEEPSEEK_API_KEY`: only required for agentic dsh turns.

Install `.[platform,postgres]` for a production process. The database user behind `AGENT3_READ_REPLICA_DSN` must be read-only even though the backend also starts a `READ ONLY` transaction.

## Identity headers

The trusted proxy may inject:

- `X-Principal: alice`
- `X-Roles: analyst,pilot-region-user`
- `X-Data-Scopes: region_code=4403|4401;org_id=001`
- `X-Scope-Version: 18`
- `X-Auth-Proxy-Token: <shared-secret>`

These values are host-side facts. They are never accepted from the model and the frontend should never attempt to construct them.

## Query path

```text
question
  -> DeterministicQuestionInterpreter
  -> Semantic/Metadata grounding
  -> Programmatic TaskRouter
      -> Query Engine: Semantic compile -> Policy IR -> trusted validation -> read-only execution
      -> dsh: filtered handoff context -> DeepSeek Official -> Agent3 MCP
```

Missing snapshot dates, ambiguous dimensions or unknown metrics become Business HITL/refusal rather than guessed SQL.

## Persistence and replay

When `AGENT3_PLATFORM_POSTGRES_DSN` is configured, the API creates four canonical tables: conversation, message, event and clarification. Event `seq` is monotonic and drives SSE `Last-Event-ID` replay. dsh session state is not the source of truth.

Without that DSN the service uses in-memory stores for local development only.

## Remaining environment acceptance

Repository CI validates contracts and security invariants without external secrets. A release environment still has to prove: organization SSO header integration, real read-replica connectivity, organization-approved DLP/egress classification, real DeepSeek API turns, and multi-user load/timeout behavior.
