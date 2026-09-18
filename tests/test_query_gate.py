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
        expect_llm=False,
    )
    observation = QueryCapabilityObservation(
        task_id=task.id,
        route="query_engine",
        metric_id="loan_balance",
        tables=("dw.dwd_loan_snapshot",),
        semantic_valid=True,
        execution_match=True,
        scope_disclosed=True,
        llm_used=False,
    )

    score = score_query_case(task, observation)

    assert score.passed is True
    assert score.checks["column_grounding"] is None
    assert score.checks["scope_disclosure"] is True
    assert score.checks["real_llm"] is None


def test_agentic_case_requires_real_llm_when_designated() -> None:
    task = QueryCapabilityTask(
        id="analysis",
        question="为什么下降",
        expected_route="agentic_analysis",
        expect_llm=True,
    )
    without_llm = QueryCapabilityObservation(task_id="analysis", route="agentic_analysis", llm_used=False)
    with_llm = QueryCapabilityObservation(task_id="analysis", route="agentic_analysis", llm_used=True)

    assert score_query_case(task, without_llm).passed is False
    assert score_query_case(task, with_llm).passed is True


def test_query_gate_report_does_not_hide_missing_observation() -> None:
    tasks = [
        QueryCapabilityTask(id="a", question="q1", expected_route="query_engine"),
        QueryCapabilityTask(id="b", question="q2", expected_route="agentic_analysis", expect_llm=True),
    ]
    observations = [
        QueryCapabilityObservation(task_id="a", route="query_engine", llm_used=False),
    ]

    report = build_query_gate_report(tasks, observations)

    assert report.case_count == 2
    assert report.passed_count == 1
    assert report.pass_rate == 0.5
    assert report.metrics["route"] == 1.0
    assert "real_llm" not in report.metrics
    missing = next(score for score in report.scores if score.task_id == "b")
    assert missing.error == "missing observation"
