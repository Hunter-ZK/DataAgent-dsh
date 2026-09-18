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

### Windows: bootstrap local DeepSeek Harness

The repository does **not** treat `dsh/profile/cordis.patch.yml` as an automatically existing dsh profile. A custom `dataagent` profile must first be created under the Harness Home.

The bootstrap/start scripts now use the same Home resolution as DeepSeek Harness itself:

```text
explicit DSH_HOME > ~/.dsh
```

So on a normal Windows account the profile lives under:

```text
C:\Users\<you>\.dsh\profiles\dataagent
```

Run once:

```powershell
.\scripts\setup_dataagent.ps1
```

The script is idempotent and self-healing. It installs pinned dependencies, creates the custom profile when missing, repairs an incomplete/unloadable local profile left by a failed previous attempt, installs the local Guard bundle, applies the repository profile patch, and validates the effective dsh configuration.

Then provide your DeepSeek official API key:

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
```

Start Agent3 MCP in another terminal:

```powershell
.\.venv\Scripts\Activate.ps1
$env:AGENT3_MCP_POC_MODE = "1"
python -m agent3.adapters.mcp.server
```

Start the local Harness:

```powershell
.\scripts\start_dataagent.ps1
```

`start_dataagent.ps1` always runs a lightweight profile self-check before launching Harness, so a missing or stale `dataagent` profile is repaired automatically.

The deployment shape is:

```text
Local browser
  -> Local DeepSeek Harness
  -> DeepSeek official API
  -> Local Agent3 MCP
  -> Local Agent3 Core
```

For the full **Windows local acceptance with a real LLM + MCP + Human-in-the-Loop**, follow [`docs/LOCAL_ACCEPTANCE.md`](docs/LOCAL_ACCEPTANCE.md).

## DeepSeek Harness

The repository pins `@deepseek-ai/dsh` to `0.1.6-alpha.2` in `dsh/package.json`. The local Harness uses its native `deepseek-official` provider with `DEEPSEEK_API_KEY`; no local model server, `LOCAL_LLM_KEY`, or `127.0.0.1:8100` endpoint is required. The DataAgent profile disables DeepSeek session upload, telemetry, web search/fetch and the web tool, connects Agent3 over streamable HTTP MCP, and loads the local guard plugin.

Before deployment run `scripts/setup_dataagent.ps1` and inspect the generated effective config. Configuration is not accepted as proof of production network isolation; deployment firewalls still own that boundary.

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
dsh/                        pinned dsh runtime + profile template + restricted query preset
guard-plugin/               dsh Cordis guard/audit glue
semantic_models/            Git source of truth for semantic definitions
benchmarks/                  public synthetic evaluation seeds
tests/                       release and architecture gates
scripts/setup_dataagent.ps1  idempotent/self-healing local profile bootstrap
scripts/start_dataagent.ps1  self-checking local Harness launcher
```

See `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/MIGRATION.md`, and `docs/LOCAL_ACCEPTANCE.md` for design boundaries, migration status, and local acceptance.
