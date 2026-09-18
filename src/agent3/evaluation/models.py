from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvalTask:
    id: str
    question: str
    golden_sql: str
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunResult:
    task_id: str
    sql: str | None
    error: str | None = None
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvalCaseResult:
    task_id: str
    passed: bool
    generated_sql: str | None
    execution_match: bool
    error: str | None
    attribution: dict[str, Any]
