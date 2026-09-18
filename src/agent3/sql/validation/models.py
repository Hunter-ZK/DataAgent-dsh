from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    suggestion: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    dialect: str
    issues: tuple[ValidationIssue, ...]
    normalized_sql: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "dialect": self.dialect, "issues": [i.to_dict() for i in self.issues], "normalized_sql": self.normalized_sql}
