# Agent3.0 -> DataAgent-dsh migration

## Source baseline

Migration behavior is based on the previously release-hardened Agent3.0 branch:

- repository: `Hunter-ZK/Agent3.0`;
- branch: `v1-release-hardening-20260913`;
- commit: `3189fa29da312ba216afa474b9f92f6380363932`;
- prior regression status: 133 Python tests passed, including trusted SQL and PySpark simulation gates.

This repository does **not** copy the old Git history. It deliberately starts with a clean public history so deleted private DB/Excel/private-benchmark objects from the old repository cannot reappear through Git history.

## Capability mapping

| Agent3.0 capability | DataAgent-dsh destination | V1 state |
|---|---|---|
| sqlglot SQL analysis | `agent3.sql.analysis` | migrated as clean Core |
| deterministic / metadata validation | `agent3.sql.validation` | migrated |
| Metadata DTO/provider contract | `agent3.metadata` | simplified V1 port |
| semantic metric compiler | `agent3.semantic` | narrowed to V1 four-field contract |
| trusted SQL quality gate | `validate_sql` Core service | retained as deterministic gate |
| Explain program facts | `explain_sql` | deterministic structured projection |
| Human approval concept | dsh approval for writes + Core approval requirement for verified SQL | retained at boundary |
| local simulator | `ExecutionBackend` | replaced by explicit Stage-0 DuckDB port |
| LangGraph Text-to-SQL runtime | split: deterministic standard-query line + dsh agentic line | architecture changed intentionally |
| CLI | `agent3.adapters.cli` | retained as thin adapter |

LLM Review/Fix/Optimize is not copied as a second domain engine. Under the new baseline, deterministic Core validation owns correctness; dsh/model behavior uses structured validator issues as repair evidence. This removes duplicated orchestration from Core.

## What is deliberately not migrated

- private metadata SQLite databases;
- raw Excel dictionaries;
- private production SQL benchmarks;
- old evaluation outputs that could be mistaken for the new architecture's benchmark;
- production credentials or `.env` files.
