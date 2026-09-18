from agent3.contracts.authz import AuthzContext
from agent3.services.factory import build_demo_core


def codes(result: dict) -> set[str]:
    return {issue["code"] for issue in result["issues"]}


def issue(result: dict, code: str) -> dict:
    return next(item for item in result["issues"] if item["code"] == code)


def test_valid_metric_sql_passes() -> None:
    sql = "SELECT org_id, SUM(balance_amt) AS loan_balance FROM dw.dwd_loan_snapshot WHERE status <> 'cancelled' AND dt = '2026-08-31' GROUP BY org_id"
    result = build_demo_core().validate_sql(AuthzContext.system(), sql, metric_id="loan_balance")
    assert result["valid"] is True
    assert "METRIC_MISMATCH" not in codes(result)


def test_metric_mandatory_filter_and_time_additivity_are_enforced() -> None:
    sql = "SELECT SUM(balance_amt) AS loan_balance FROM dw.dwd_loan_snapshot WHERE dt IN ('2026-07-31', '2026-08-31')"
    result = build_demo_core().validate_sql(AuthzContext.system(), sql, metric_id="loan_balance")
    assert result["valid"] is False
    assert {"MISSING_MANDATORY_FILTER", "NON_ADDITIVE_OVER_TIME"} <= codes(result)


def test_unknown_table_and_column_fail_closed() -> None:
    core = build_demo_core()
    result = core.validate_sql(AuthzContext.system(), "select imaginary from dw.dwd_loan_snapshot where dt='2026-08-31'")
    assert result["valid"] is False
    assert "UNKNOWN_COLUMN" in codes(result)
    missing = core.validate_sql(AuthzContext.system(), "select x from dw.no_such_table")
    assert "UNKNOWN_TABLE" in codes(missing)


def test_drop_uses_mature_agent3_blocking_contract() -> None:
    result = build_demo_core().validate_sql(AuthzContext.system(), "drop table dw.dwd_loan_snapshot")
    assert result["valid"] is False
    assert "DROP_OR_TRUNCATE" in codes(result)
    assert issue(result, "DROP_OR_TRUNCATE")["action"] == "block"
    assert issue(result, "DROP_OR_TRUNCATE")["blocking"] is True


def test_maxcompute_insert_overwrite_missing_table_preserves_auto_fix_contract() -> None:
    result = build_demo_core().validate_sql(
        AuthzContext.system(),
        "INSERT OVERWRITE dw.dwd_loan_snapshot SELECT '2026-08-31', 'A', '440300', 'P', 10, 'active'",
    )
    assert result["valid"] is False
    item = issue(result, "MAXCOMPUTE_INSERT_OVERWRITE_TABLE_REQUIRED")
    assert item["action"] == "auto_fix"
    assert item["auto_fixable"] is True
    assert item["blocking"] is True
    assert "TABLE" in item["suggestion"]


def test_advisory_partition_warning_does_not_block_trusted_candidate() -> None:
    result = build_demo_core().validate_sql(
        AuthzContext.system(),
        "SELECT org_id, balance_amt FROM dw.dwd_loan_snapshot",
    )
    assert "NO_PARTITION_FILTER" in codes(result)
    warning = issue(result, "NO_PARTITION_FILTER")
    assert warning["action"] == "advisory"
    assert warning["blocking"] is False
    assert result["valid"] is True


def test_multiple_statements_fail_closed() -> None:
    result = build_demo_core().validate_sql(
        AuthzContext.system(),
        "SELECT 1; DROP TABLE dw.dwd_loan_snapshot",
    )
    assert result["valid"] is False
    assert codes(result) == {"MULTI_STATEMENT_NOT_ALLOWED"}
