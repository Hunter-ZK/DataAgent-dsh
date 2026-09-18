from agent3.evaluation.query_gate import (
    QueryCapabilityObservation,
    QueryCapabilityTask,
    build_query_gate_report,
    score_query_case,
)


def test_query_case_scores_only_exercised_checks() -> None:
    task = QueryCapabilityTask(
        id="loan-balance",
        question="深圳贷款余额是多少",
        expected_route="query_engine",
        expected_metric_id="loan_balance",
        expected_tables=("dw.dwd_loan_snapshot",),
        expect_scope_disclosure=True,
    )
    observation = QueryCapabilityObservation(
        task_id=task.id,
        route="query_engine",
        metric_id="loan_balance",
        tables=("dw.dwd_loan_snapshot",),
        semantic_valid=True,
        execution_match=True,
        scope_disclosed=True,
        llm_used=True,
    )

    score = score_query_case(task, observation)

    assert score.passed is True
    assert score.checks["column_grounding"] is None
    assert score.checks["scope_disclosure"] is True


def test_query_gate_report_does_not_hide_missing_observation() -> None:
    tasks = [
        QueryCapabilityTask(id="a", question="q1", expected_route="query_engine"),
        QueryCapabilityTask(id="b", question="q2", expected_route="agentic_analysis"),
    ]
    observations = [
        QueryCapabilityObservation(task_id="a", route="query_engine", llm_used=True),
    ]

    report = build_query_gate_report(tasks, observations)

    assert report.case_count == 2
    assert report.passed_count == 1
    assert report.pass_rate == 0.5
    assert report.metrics["route"] == 1.0
    assert report.metrics["real_llm"] == 1.0
    missing = next(score for score in report.scores if score.task_id == "b")
    assert missing.error == "missing observation"
