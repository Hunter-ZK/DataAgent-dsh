from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DataScope:
    """One enforced authorization dimension."""
    dim: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.dim.strip() or not self.values:
            raise ValueError("DataScope requires dim and at least one value")


@dataclass(frozen=True, slots=True)
class AuthzContext:
    """Trusted identity context injected by host infrastructure, never the model."""
    principal: str
    roles: tuple[str, ...] = ()
    data_scopes: tuple[DataScope, ...] = ()
    session_id: str | None = None
    purpose: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.principal.strip():
            raise ValueError("principal must be non-empty")

    @classmethod
    def system(cls, *, purpose: str = "evaluation") -> "AuthzContext":
        return cls(principal="system", roles=("system",), purpose=purpose)
