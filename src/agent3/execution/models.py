from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    max_rows: int = 1000
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_rows < 1:
            raise ValueError("max_rows must be >= 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")


@dataclass(frozen=True, slots=True)
class ResultSet:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)
