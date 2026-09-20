# Security baseline

DeepSeek Harness is treated as untrusted/replaceable runtime infrastructure, not as the enterprise security boundary.

## 1. Mandatory deployment invariants

| ID | Invariant |
| --- | --- |
| INV-S01 | dsh must not hold production database credentials |
| INV-S02 | dsh must not have a network route to production databases |
| INV-S03 | every database access must cross the Agent3 controlled service boundary |
| INV-S04 | production identity must come from a trusted SSO/reverse-proxy boundary |
| INV-S05 | browser/model inputs must not set principal, role or data scope |
| INV-S06 | read-only execution must use a read-only database role in addition to application enforcement |
| INV-S07 | model egress is restricted to approved DeepSeek Official traffic and approved content categories |

These are infrastructure requirements. Passing unit tests cannot prove network isolation, database privileges or enterprise DLP compliance.

## 2. Production identity

`TrustedProxyIdentityResolver` requires:

- `X-Principal`;
- optional `X-Roles`;
- optional `X-Data-Scopes`;
- optional `X-Scope-Version`;
- `X-Auth-Proxy-Token` matching `AGENT3_PROXY_SHARED_SECRET`.

The upstream trusted proxy must authenticate the user, strip any browser-supplied identity headers, inject trusted values, and add the proxy token. `agent3-api` rejects missing/invalid proxy identity.

The model never receives a tool argument that can choose principal, role or scope.

## 3. Local acceptance identity

Local acceptance has a separate explicit mode:

```text
AGENT3_DEV_AUTH=1
```

It exists only so a developer can test the full React → API → dsh/MCP path without installing enterprise SSO first.

Security properties:

- the composition root refuses `AGENT3_DEV_AUTH` when `AGENT3_HOST` is not loopback;
- browser-supplied identity headers are ignored;
- a fixed local principal/role/scope is constructed host-side;
- the mode is visibly tagged `auth_mode=local-dev`;
- production mode still requires `AGENT3_PROXY_SHARED_SECRET`.

Never deploy `AGENT3_DEV_AUTH=1` to a shared machine, VM, container endpoint or non-loopback listener.

## 4. Authorization and Policy IR

`AuthzContext` is injected by the trusted host boundary. Central policies are represented as Policy IR and compiled into SQL AST predicates.

Identity data scopes and matching central policies are intersected. Empty intersections deny the query. Multi-table propagation that cannot be proven safe must fail closed.

`scope_version` is carried as trusted identity metadata so future enterprise token/session adapters can invalidate stale authorization after permission changes.

## 5. Query execution

The read-only backend is not exposed as a free-form model tool. The standard path is:

```text
Grounded QueryIR
 -> SemanticCompiler
 -> Policy compiler
 -> deterministic SQL validation
 -> read-only ExecutionBackend
```

The PostgreSQL backend starts a read-only transaction and applies row/time limits, but the database role itself must still be read-only. Prefer a replica or isolated query database for the pilot.

## 6. DeepSeek Official egress

The current pilot is **not offline**. DeepSeek Harness runs locally, while inference uses the DeepSeek Official API.

The intended network model is:

```text
Default deny egress
+ explicitly approved DeepSeek Official endpoint(s)
```

Generic dsh web search/fetch/tool surfaces are disabled in the restricted query profile.

Before content becomes model-visible, it must pass the LLM egress boundary. Current denied categories include:

- credentials/tokens;
- identity/authz state;
- obvious personal identifiers caught by the conservative text gate;
- raw row-detail result data by default.

Approved schema/semantic evidence and suitably classified aggregate information may be model-visible.

The current regex/text classifier is a pilot guard only. Real financial-data deployment requires organization-approved DLP/classification rules and an explicit data-egress review.

## 7. Prompt injection

Metadata, historical SQL, query results and other retrieved material are evidence, not instructions. Prompt wrappers and warning scanners are defense in depth only. Security must still hold if the model follows malicious retrieved text.

Authorization, SQL validation, policy compilation and execution limits therefore remain host-controlled.

## 8. dsh query runtime

The `dataagent-query-sdk` path is intentionally restricted. It disables developer mutation surfaces including shell, PowerShell, filesystem write-oriented tooling, jobs, plugin management and generic web access.

Business clarification is owned by `agent3-api`; it does not depend on dsh Tool Approval.

Tool Approval Bridge is deferred until a future warehouse-development profile intentionally exposes write-capable tools.

## 9. Guard plugin

The existing Cordis guard remains defense in depth for the legacy/local dsh Web path. It is not the primary enterprise security boundary and must not be used as evidence that production database isolation is complete.

## 10. Release evidence still required outside CI

Before a real pilot:

- verify trusted proxy/SSO header stripping and injection;
- verify read-replica account privileges independently from application code;
- verify firewall rules block dsh → production database connectivity;
- verify outbound traffic is restricted to approved DeepSeek endpoints;
- complete enterprise DLP/data-egress review;
- test multiple principals with conflicting scopes and confirm zero cross-user leakage.
