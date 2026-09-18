from pathlib import Path

import pytest

from agent3.contracts.authz import AuthzContext
from agent3.metadata.demo import build_demo_metadata
from agent3.query.interpreter import DeterministicQuestionInterpreter
from agent3.query.models import QueryClarification, QueryRefusal, QueryUnderstandingStatus
from agent3.routing.models import TaskType
from agent3.semantic.compiler import SemanticCompileError
from agent3.semantic.models import QueryIR
from agent3.semantic.registry import SemanticRegistry
from agent3.services.factory import build_demo_core


ROOT = Path(__file__).resolve().parents[1]


def _interpreter() -> DeterministicQuestionInterpreter:
    return DeterministicQuestionInterpreter(
        SemanticRegistry.from_yaml(ROOT / "semantic_models" / "loan.yaml"),
        build_demo_metadata(),
    )


def test_standard_question_is_grounded_without_llm() -> None:
    result = _interpreter().interpret(
        AuthzContext.system(),
        "2026年8月31日深圳市贷款余额是多少？",
    )

    assert result.status is QueryUnderstandingStatus.READY
    assert result.task_contract.task_type is TaskType.STANDARD_QUERY
    assert result.task_contract.ir_valid is True
    assert result.query_ir is not None
    assert result.query_ir.metric_id == "loan_balance"
    assert result.query_ir.time_values == ("2026-08-31",)
    assert result.query_ir.filters[0].field == "region_code"
    assert result.query_ir.filters[0].value == "4403"
    assert result.llm_used is False


def test_grouping_dimension_is_grounded_from_semantic_vocabulary() -> None:
    result = _interpreter().interpret(
        AuthzContext.system(),
        "按地区看2026-08-31贷款余额",
    )

    assert result.status is QueryUnderstandingStatus.READY
    assert result.query_ir is not None
    assert result.query_ir.dimensions == ("region_code",)


def test_snapshot_metric_without_date_requires_business_clarification() -> None:
    result = _interpreter().interpret(AuthzContext.system(), "深圳贷款余额是多少？")

    assert isinstance(result, QueryClarification)
    assert result.status is QueryUnderstandingStatus.NEED_CLARIFICATION
    assert result.missing_context == ("time",)
    assert "具体日期" in result.question


def test_unknown_metric_refuses_instead_of_inventing_schema() -> None:
    result = _interpreter().interpret(AuthzContext.system(), "查询神秘指标的值")

    assert isinstance(result, QueryRefusal)
    assert result.status is QueryUnderstandingStatus.REFUSED
    assert "refusing to invent" in result.reason


def test_why_question_is_grounded_but_routed_exploratory() -> None:
    result = _interpreter().interpret(
        AuthzContext.system(),
        "为什么2026-08-31深圳贷款余额下降？",
    )

    assert result.status is QueryUnderstandingStatus.EXPLORATORY
    assert result.task_contract.task_type is TaskType.EXPLORATORY_ANALYSIS
    assert result.query_ir is not None
    assert result.query_ir.metric_id == "loan_balance"


def test_compiler_rejects_unbounded_non_additive_metric() -> None:
    core = build_demo_core()
    with pytest.raises(SemanticCompileError, match="explicit snapshot"):
        core.compile_query(AuthzContext.system(), QueryIR(metric_id="loan_balance"))
