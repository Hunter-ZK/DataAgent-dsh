# DataAgent-dsh

DataAgent-dsh is the platformized Agent3.0 implementation built around one hard boundary:

> **DeepSeek Harness is a replaceable local Agent Runtime; Agent3 is the harness-agnostic Data Intelligence Core.**

The current pilot architecture uses a local DeepSeek Harness runtime with the DeepSeek Official API. Standard semantic queries stay on the deterministic Query Engine path; exploratory analysis is delegated to dsh. `agent3-api` owns canonical conversation history and stable SSE events.

## Current delivery scope

Implemented on `upgrade/platform-p0-a`:

- **P0-Q Query Capability Gate** — route, metric/schema grounding, semantic validity, execution accuracy, clarification/refusal, caveat/scope disclosure and agentic-LLM evidence;
- **Query Understanding** — conservative natural-language grounding into READY / CLARIFICATION / REFUSAL / EXPLORATORY outcomes;
- **Programmatic Task Router** — the model does not own final routing;
- **Agent3 Core** — Metadata, Semantic Model, Trusted SQL, Policy IR and read-only Execution ports;
- **Query Engine** — Semantic compile → Policy compile → deterministic validation → optional read-only execution;
- **agent3-api** — canonical conversation owner, Business HITL, SSE replay and dsh SDK orchestration;
- **DeepSeek Harness Python SDK** — pinned SDK runtime, DeepSeek Official provider and restricted query profile;
- **Identity boundary** — Trusted Proxy in deployed environments, explicit loopback-only Local Dev Identity for acceptance;
- **LLM egress controls** — conservative prompt/result boundary with sensitive categories denied by default;
- **PostgreSQL persistence** — canonical conversation/message/event/clarification stores;
- **React pilot shell** — conversation UI, SSE events, SQL/result/caveat/scope/refusal/clarification display;
- **read-only PostgreSQL backend** — optional production/read-replica execution port;
- **CI** — Python/Core/SDK/dsh/Guard gates plus React/Vite build gate.

Deferred by design:

- Superset embedding;
- Tool Approval Bridge / `dataagent-dev-sdk`;
- warehouse-development UI;
- organization-specific SSO/LDAP implementation;
- organization-approved enterprise DLP;
- real production metadata/semantic assets and real read-replica credentials.

## Architecture

```text
Browser / React Shell
        |
Trusted SSO / Reverse Proxy        Local acceptance only:
        |                           loopback Local Dev Identity
        +-------------+-------------+
                      |
                 agent3-api
        Canonical conversation owner
                      |
              Query Understanding
                      |
             Programmatic Router
              /                \
     standard query        exploratory
          |                    |
      Query Engine          dsh SDK
          |                    |
 Semantic Compiler       DeepSeek Official API
          |                    |
      Policy IR              MCP
          |                    |
 Trusted SQL Gate       Agent3 Core Tools
          |
 Read-only Execution
```

`src/agent3` is Core and may not import `agent3_api`, FastAPI, MCP or dsh. CI enforces the dependency direction.

## Security invariants

The deployment is invalid if any of these is false:

- dsh has no production database credentials;
- dsh has no network route to production databases;
- every database access crosses the Agent3 controlled service boundary;
- production identity comes from a trusted SSO/reverse-proxy boundary, never browser/model arguments;
- Local Dev Identity is explicit and may bind only to loopback;
- DeepSeek Official API is the only intended model egress for the current pilot; identity/authz/credentials and raw row-detail data are not model-visible by default;
- read-only execution is protected both by application policy and a read-only database role.

## Local acceptance — recommended next step

Prerequisites:

- Windows PowerShell;
- Python 3.14;
- Node.js 24+ / npm;
- a valid `DEEPSEEK_API_KEY`.

From the repository root on `upgrade/platform-p0-a`:

```powershell
git checkout upgrade/platform-p0-a
git pull origin upgrade/platform-p0-a
$env:DEEPSEEK_API_KEY = "sk-..."
.\scripts\start_platform.ps1
```

The launcher creates/uses `.venv`, installs the platform/MCP and web dependencies, starts the local Agent3 MCP, starts `agent3-api` in **loopback-only Local Dev Identity mode**, and starts the React/Vite shell.

Open:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies `/api` to `127.0.0.1:8080`; the browser never needs to construct production identity headers.

For detailed acceptance steps, use [`docs/LOCAL_ACCEPTANCE.md`](docs/LOCAL_ACCEPTANCE.md).

## Production/pilot composition

Production mode does **not** use `AGENT3_DEV_AUTH`. It requires a trusted SSO/reverse proxy and `AGENT3_PROXY_SHARED_SECRET`. See [`docs/PLATFORM_PILOT.md`](docs/PLATFORM_PILOT.md) and [`docs/SECURITY.md`](docs/SECURITY.md).

## Repository map

```text
src/agent3/                  harness-agnostic Data Intelligence Core
  query/                     deterministic Query Understanding
  metadata/                  Metadata providers and approved assets
  semantic/                  Metric/dimension registry + compiler
  policy/                    Policy IR + SQL compiler + egress contract
  sql/                       SQLGlot analysis and validation
  execution/                 DuckDB eval + read-only PostgreSQL backend
  evaluation/                Stage-0 and P0-Q evaluation contracts
  routing/                   Programmatic Task Router

src/agent3_api/              platform/application layer
  app.py                     REST/SSE surface
  orchestrator.py            canonical turn orchestration
  harness_runtime.py         local dsh SDK runtime pool
  auth.py                    trusted proxy + local acceptance identity
  persistence.py             PostgreSQL conversation/event/HITL stores

web/                         React pilot shell
dsh/sdk/                     restricted SDK invocation patch
dsh/presets/                 query presets
guard-plugin/                defense-in-depth dsh guard
metadata_models/             example approved physical metadata
semantic_models/             example semantic definitions
policies/                    Policy IR assets
benchmarks/                  P0-Q evaluation seeds
scripts/start_platform.ps1   one-command local acceptance launcher
```

Key documents:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/SECURITY.md`](docs/SECURITY.md)
- [`docs/LOCAL_ACCEPTANCE.md`](docs/LOCAL_ACCEPTANCE.md)
- [`docs/PILOT_ACCEPTANCE.md`](docs/PILOT_ACCEPTANCE.md)
- [`docs/PLATFORM_PILOT.md`](docs/PLATFORM_PILOT.md)
- [`docs/MIGRATION.md`](docs/MIGRATION.md)
