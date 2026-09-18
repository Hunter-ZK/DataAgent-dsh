from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueAction(StrEnum):
    """Trusted SQL routing semantics preserved from Agent3.0.

    Severity is presentation/risk strength; action is the workflow fact. In particular,
    AUTO_FIX and BLOCK are both blocking for automatic trust, while ADVISORY is not.
    """

    AUTO_FIX = "auto_fix"
    CONTEXT_REQUIRED = "context_required"
    HUMAN_REVIEW = "human_review"
    BLOCK = "block"
    ADVISORY = "advisory"
    IGNORE = "ignore"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    suggestion: str | None = None
    metadata: dict[str, Any] | None = None
    action: IssueAction = IssueAction.BLOCK
    auto_fixable: bool = False

    @property
    def blocking(self) -> bool:
        return self.action in {
            IssueAction.AUTO_FIX,
            IssueAction.CONTEXT_REQUIRED,
            IssueAction.HUMAN_REVIEW,
            IssueAction.BLOCK,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        data["action"] = self.action.value
        data["blocking"] = self.blocking
        return data


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    dialect: str
    issues: tuple[ValidationIssue, ...]
    normalized_sql: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "dialect": self.dialect,
            "issues": [i.to_dict() for i in self.issues],
            "normalized_sql": self.normalized_sql,
        }
