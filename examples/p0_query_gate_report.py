from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from agent3.evaluation.query_gate import (
    QueryCapabilityObservation,
    QueryCapabilityTask,
    build_query_gate_report,
)


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_tasks(path: Path) -> list[QueryCapabilityTask]:
    tasks: list[QueryCapabilityTask] = []
    for row in _read_jsonl(path):
        tasks.append(
            QueryCapabilityTask(
                id=row["id"],
                question=row["question"],
                expected_route=row["expected_route"],
                expected_metric_id=row.get("expected_metric_id"),
                expected_tables=tuple(row.get("expected_tables", [])),
                expected_columns=tuple(row.get("expected_columns", [])),
                expect_clarification=bool(row.get("expect_clarification", False)),
                expect_refusal=bool(row.get("expect_refusal", False)),
                expected_caveats=tuple(row.get("expected_caveats", [])),
                expect_scope_disclosure=bool(row.get("expect_scope_disclosure", False)),
                expect_llm=bool(row.get("expect_llm", False)),
                metadata=row.get("metadata", {}),
            )
        )
    return tasks


def load_observations(path: Path) -> list[QueryCapabilityObservation]:
    observations: list[QueryCapabilityObservation] = []
    for row in _read_jsonl(path):
        observations.append(
            QueryCapabilityObservation(
                task_id=row["task_id"],
                route=row.get("route"),
                metric_id=row.get("metric_id"),
                tables=tuple(row.get("tables", [])),
                columns=tuple(row.get("columns", [])),
                sql=row.get("sql"),
                semantic_valid=row.get("semantic_valid"),
                execution_match=row.get("execution_match"),
                clarification_asked=bool(row.get("clarification_asked", False)),
                refused=bool(row.get("refused", False)),
                caveats=tuple(row.get("caveats", [])),
                scope_disclosed=bool(row.get("scope_disclosed", False)),
                llm_used=bool(row.get("llm_used", False)),
                error=row.get("error"),
                trace=row.get("trace", {}),
            )
        )
    return observations


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the P0-Q business-query capability report")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--min-pass-rate", type=float, default=None)
    args = parser.parse_args()

    report = build_query_gate_report(load_tasks(args.tasks), load_observations(args.observations))
    payload = {
        "case_count": report.case_count,
        "passed_count": report.passed_count,
        "pass_rate": report.pass_rate,
        "metrics": report.metrics,
        "exercised": report.exercised,
        "scores": [asdict(score) for score in report.scores],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.min_pass_rate is not None and report.pass_rate < args.min_pass_rate:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
