# Security baseline

DeepSeek Harness is treated as untrusted/replaceable execution infrastructure, not as the enterprise security boundary.

## Deployment invariants

| ID | Mandatory invariant |
|---|---|
| INV-S01 | dsh runtime must not hold production database credentials |
| INV-S02 | dsh runtime must not have a network route to production databases |
| INV-S03 | all database access must cross the Agent3 controlled service boundary |

These are infrastructure requirements. A passing unit test cannot replace network or identity enforcement.

## Identity

Every public Core method takes `AuthzContext` as its first argument. MCP model-visible schemas do not accept principal/role/data-scope parameters; an adapter gets identity from a trusted session/service boundary.

The included streamable-HTTP MCP server is **PoC-only**. Static identity requires `AGENT3_MCP_POC_MODE=1`. Production composition must replace that provider with authenticated identity propagation and service-to-service authentication.

## V1 row authorization

V1 supports one row-scope dimension and rewrites SQL at the AST layer. Multi-table queries under a row scope are rejected because correct scope propagation needs the later complete Policy Engine.

## Prompt injection

Metadata, historical SQL and query results are `Retrieved Evidence`, never instruction context. The Core includes a heuristic warning scanner, but this is not a security control. Authorization and controlled execution must remain effective even when the model follows malicious retrieved text.

## dsh guard plugin

The plugin performs three defense-in-depth functions:

- monotonic `ctx.tools.guard()` blocks shell database clients;
- `tools/pre-execute` routes write tools to approval and accepts only `allowed-once`;
- `tools/result` emits a sanitized audit payload.

It deliberately drops raw SQL and credential-looking values from the general audit payload.

## Offline deployment

The profile disables the default external session-log, telemetry, web-search, web-fetch and web-tool lines and sets `DSH_TELEMETRY_MODE=DISABLED`. Release verification must additionally inspect the merged `--dump-config` output and observe network egress in an isolated environment.
