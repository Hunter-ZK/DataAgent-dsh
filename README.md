# DataAgent-dsh

DataAgent-dsh is the V2/V1 implementation line of Agent3.0 rebuilt around one boundary:

> **DeepSeek Harness is a replaceable Agent Runtime; Agent3 is a harness-agnostic Data Intelligence Core.**

The repository starts from the validated Agent3.0 capability baseline (`v1-release-hardening-20260913`, source commit `3189fa29da312ba216afa474b9f92f6380363932`) but creates a clean history and a new package layout. Private data, historical database files, and private benchmark assets are not migrated.

## Current V1 scope

This repository implements the delivery line intentionally limited to:

- Stage 0 — reproducible evaluation + read-only `ExecutionBackend` using DuckDB;
- Stage 1 — independent Agent3 Core;
- Stage 2 — thin MCP / HTTP / CLI adapters;
- Stage 3 — DeepSeek Harness integration assets and guard plugin PoC;
- minimal Stage 4B semantic model: `aggregation`, `measure`, `mandatory_filters`, `additivity.time`;
- `AuthzContext` on every Core public method and one-dimension AST row filtering.

Production database execution, a complete Policy Engine, general multi-table semantic compilation, production DDL execution, and enterprise approval/audit storage are explicitly deferred.

## Architecture

```text
User / API / dsh
      |
  Task Contract
      |
 +----+------------------+
 |                       |
standard_query       exploratory/dev
 |                       |
Semantic Query       DeepSeek Harness
Engine               Agent Loop + Skills
 |                       |
 +----------+------------+
            |
       Tool Adapters
      MCP / HTTP / CLI
            |
        Agent3 Core
            |
   +--------+---------+
   |                  |
Semantic/Metadata  SQL/Policy
   |                  |
   +--------+---------+
            |
      Execution Port
            |
      Eval Backend
       (DuckDB V1)
```

Core code lives in `src/agent3` and may not import MCP, FastAPI, or dsh. CI enforces this with `scripts/check_architecture.py`.

## Security invariants

The deployment is invalid if any of these is false:

- **INV-S01** — dsh runtime has no production database credentials.
- **INV-S02** — dsh runtime has no network route to production databases.
- **INV-S03** — every database access crosses the Agent3 controlled service boundary.

The dsh guard plugin is defense in depth and audit glue, not the production security boundary.

## Quick start

Python 3.14 is the compatibility baseline inherited from Agent3.0.

```bash
python -m pip install -e '.[all]'
python -m pytest
python scripts/check_architecture.py
python examples/stage0_eval.py
```

MCP PoC is intentionally blocked unless explicitly enabled:

```bash
export AGENT3_MCP_POC_MODE=1
python -m agent3.adapters.mcp.server
```

That mode uses a static PoC identity and MUST NOT be used for production deployment.

## DeepSeek Harness

The repository pins `@deepseek-ai/dsh` to `0.1.6-alpha.2` in `dsh/package.json`. The deployment profile disables DeepSeek session upload, telemetry, web search/fetch and the web tool, points inference at an internal OpenAI-compatible service, connects Agent3 over streamable HTTP MCP, and loads the local guard plugin.

Before deployment run `dsh --profile dataagent --dump-config`, then verify **zero public egress** with an outbound firewall log or packet capture. Configuration is not accepted as proof of isolation.

## Repository map

```text
src/agent3/                 harness-agnostic Python Core
  contracts/                AuthzContext and stable contracts
  metadata/                 table/column metadata ports
  semantic/                 metric registry + deterministic compiler
  sql/                      sqlglot analysis and validation
  policy/                   V1 AST row-filter policy
  execution/                ExecutionBackend port + DuckDB eval backend
  evaluation/               backend-independent evaluation runner
  routing/                  Task Contract routing rules
  adapters/                 MCP / HTTP / CLI protocol projections
.dsh/skills/                domain workflow instructions
dsh/                        pinned dsh runtime + profile template
guard-plugin/               dsh Cordis guard/audit glue
semantic_models/            Git source of truth for semantic definitions
benchmarks/                  public synthetic evaluation seeds
tests/                       release and architecture gates
```

See `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, and `docs/MIGRATION.md` for design boundaries and migration status.
