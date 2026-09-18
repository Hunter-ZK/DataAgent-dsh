from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PolicyOperator(StrEnum):
    IN = "in"
    EQ = "eq"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """Implementation-independent authorization rule over a business dimension."""

    dimension: str
    operator: PolicyOperator
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.dimension.strip():
            raise ValueError("policy dimension must not be empty")
        if not self.values:
            raise ValueError("policy rule must contain at least one value")
        if self.operator is PolicyOperator.EQ and len(self.values) != 1:
            raise ValueError("eq policy requires exactly one value")


@dataclass(frozen=True, slots=True)
class PrincipalSelector:
    roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PolicyIR:
    """Canonical policy source compiled into Agent3 SQL filters or BI RLS later."""

    policy_id: str
    version: int
    selector: PrincipalSelector
    rules: tuple[PolicyRule, ...]

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty")
        if self.version <= 0:
            raise ValueError("policy version must be positive")
        if not self.rules:
            raise ValueError("policy must contain at least one rule")
