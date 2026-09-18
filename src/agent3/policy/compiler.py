from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlglot import exp

from agent3.contracts.authz import AuthzContext, DataScope
from agent3.policy.ir import PolicyIR, PolicyOperator, PolicyRule, PrincipalSelector
from agent3.sql.analysis.analyzer import SQLAnalyzer


class PolicyDenied(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class PolicyApplication:
    sql: str
    policy_versions: tuple[str, ...]
    effective_scopes: tuple[DataScope, ...]


class PolicyRegistry:
    def __init__(self, policies: tuple[PolicyIR, ...] = ()) -> None:
        self._policies = policies

    def matching(self, authz: AuthzContext) -> tuple[PolicyIR, ...]:
        role_set = set(authz.roles)
        return tuple(
            policy
            for policy in self._policies
            if not policy.selector.roles or bool(role_set.intersection(policy.selector.roles))
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PolicyRegistry":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        policies: list[PolicyIR] = []
        for raw in payload.get("policies", []):
            policies.append(
                PolicyIR(
                    policy_id=str(raw["policy_id"]),
                    version=int(raw["version"]),
                    selector=PrincipalSelector(roles=tuple((raw.get("selector") or {}).get("roles", []))),
                    rules=tuple(
                        PolicyRule(
                            dimension=str(item["dimension"]),
                            operator=PolicyOperator(str(item["operator"])),
                            values=tuple(str(value) for value in item.get("values", [])),
                        )
                        for item in raw.get("rules", [])
                    ),
                )
            )
        return cls(tuple(policies))


class SQLPolicyCompiler:
    """Compile trusted identity + central Policy IR into SQL row predicates.

    V1 deliberately supports only single-table SELECT statements. Multi-table
    scope propagation is denied instead of guessed.
    """

    def __init__(self, registry: PolicyRegistry | None = None) -> None:
        self._registry = registry or PolicyRegistry()
        self._analyzer = SQLAnalyzer()

    def effective_scopes(self, authz: AuthzContext) -> tuple[DataScope, ...]:
        if "system" in authz.roles:
            return ()

        allowed: dict[str, set[str]] = {
            scope.dim: set(scope.values)
            for scope in authz.data_scopes
        }
        for policy in self._registry.matching(authz):
            for rule in policy.rules:
                values = set(rule.values)
                if rule.dimension in allowed:
                    allowed[rule.dimension].intersection_update(values)
                else:
                    allowed[rule.dimension] = values
                if not allowed[rule.dimension]:
                    raise PolicyDenied(f"policy intersection denies all values for {rule.dimension}")

        return tuple(
            DataScope(dim=dimension, values=tuple(sorted(values)))
            for dimension, values in sorted(allowed.items())
        )

    def apply(self, authz: AuthzContext, sql: str, *, dialect: str = "maxcompute") -> PolicyApplication:
        policies = self._registry.matching(authz)
        versions = tuple(f"{item.policy_id}@{item.version}" for item in policies)
        scopes = self.effective_scopes(authz)
        if not scopes:
            return PolicyApplication(sql=sql, policy_versions=versions, effective_scopes=())

        tree = self._analyzer.parse(sql, dialect=dialect)
        if not isinstance(tree, exp.Select):
            raise PolicyDenied("row policy only supports a root SELECT")
        tables = list(tree.find_all(exp.Table))
        if len(tables) != 1:
            raise PolicyDenied("row policy refuses multi-table SQL until scope propagation is explicit")

        for scope in scopes:
            column = exp.column(scope.dim)
            if len(scope.values) == 1:
                condition = exp.EQ(this=column, expression=exp.Literal.string(scope.values[0]))
            else:
                condition = exp.In(
                    this=column,
                    expressions=[exp.Literal.string(value) for value in scope.values],
                )
            tree = tree.where(condition, copy=False)

        target_dialect = "hive" if dialect in {"maxcompute", "odps", "dataworks"} else dialect
        return PolicyApplication(
            sql=tree.sql(dialect=target_dialect),
            policy_versions=versions,
            effective_scopes=scopes,
        )
