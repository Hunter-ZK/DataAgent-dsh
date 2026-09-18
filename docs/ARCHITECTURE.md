# Architecture baseline

## Frozen boundary

The only acceptable dependency direction is:

```text
DeepSeek Harness / UI / API
          -> adapters
          -> Agent3Core services
          -> domain modules and ports
```

`src/agent3` outside `adapters/` cannot import dsh, MCP, or FastAPI. Adapters cannot import sqlglot or DuckDB; they translate protocol input/output and call Core methods.

## Two execution lines

### Standard query line

A model may help parse a `TaskContract`, but routing and SQL construction are program-owned:

```text
TaskContract
 -> TaskRouter
 -> Semantic QueryIR
 -> SemanticCompiler
 -> SQLValidator
 -> candidate SQL
```

A standard query is routed here only when all are true: `task_type=standard_query`, IR is valid, and semantic coverage is above the configured threshold.

### Exploratory / warehouse development line

Open-ended analysis and development are delegated to dsh's native agent loop. dsh can call Agent3 tools but does not own semantic truth, policy, metadata, or production credentials.

## V1 semantic contract

Only four semantic controls are release gates in V1:

1. aggregation;
2. measure;
3. mandatory filters;
4. time additivity.

The compiler intentionally supports a narrow query shape. Unsupported shapes fail rather than silently falling back to model-generated SQL.

## Evaluation

Evaluation is independent of dsh. `EvaluationAdapter.run(task) -> RunResult` allows future implementations for dsh, direct Core/model, DataWorks, and bare-model baselines. `ExecutionBackend` executes golden and candidate SQL in a test backend; scoring compares result sets, not SQL text.

## Future ports already reserved

- production `ExecutionBackend` / Gateway;
- PostgreSQL + pgvector Metadata and VerifiedSQL repositories;
- complete Policy Engine and column masking;
- dsh SDK evaluation adapter;
- full semantic compiler with join paths and versioned metrics.
