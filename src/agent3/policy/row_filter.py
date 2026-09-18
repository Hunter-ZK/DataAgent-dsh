from __future__ import annotations

from sqlglot import exp
from agent3.contracts.authz import AuthzContext
from agent3.sql.analysis.analyzer import SQLAnalyzer


class PolicyError(PermissionError):
    pass


class RowFilterPolicy:
    """V1 AST policy: enforce one data-scope dimension on single-table SELECTs."""
    def __init__(self) -> None:
        self._analyzer = SQLAnalyzer()

    def apply(self, authz: AuthzContext, sql: str, *, dialect: str = "maxcompute") -> tuple[str, bool]:
        if "system" in authz.roles or not authz.data_scopes:
            return sql, False
        if len(authz.data_scopes) != 1:
            raise PolicyError("V1 supports exactly one data-scope dimension")
        tree = self._analyzer.parse(sql, dialect=dialect)
        if not isinstance(tree, exp.Select):
            raise PolicyError("V1 row policy only supports a root SELECT")
        tables = list(tree.find_all(exp.Table))
        if len(tables) != 1:
            raise PolicyError("V1 row policy refuses multi-table queries instead of guessing scope propagation")
        scope = authz.data_scopes[0]
        column = exp.column(scope.dim)
        condition = exp.EQ(this=column, expression=exp.Literal.string(scope.values[0])) if len(scope.values) == 1 else exp.In(this=column, expressions=[exp.Literal.string(v) for v in scope.values])
        tree = tree.where(condition, copy=False)
        return tree.sql(dialect="hive" if dialect in {"maxcompute", "odps", "dataworks"} else dialect), True
