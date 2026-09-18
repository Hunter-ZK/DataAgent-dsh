import pytest

from agent3.policy.egress import EgressDataClass, LLMEgressPolicy
from agent3.policy.ir import PolicyIR, PolicyOperator, PolicyRule, PrincipalSelector


def test_policy_ir_is_versioned_and_business_dimension_based() -> None:
    policy = PolicyIR(
        policy_id="region_scope",
        version=18,
        selector=PrincipalSelector(roles=("analyst_sz",)),
        rules=(PolicyRule("region", PolicyOperator.IN, ("4403",)),),
    )
    assert policy.version == 18
    assert policy.rules[0].dimension == "region"


def test_policy_eq_requires_exactly_one_value() -> None:
    with pytest.raises(ValueError):
        PolicyRule("region", PolicyOperator.EQ, ("4403", "4401"))


def test_llm_egress_denies_identity_authz_credentials_and_row_detail() -> None:
    policy = LLMEgressPolicy(k_anonymity=5)
    for data_class in (
        EgressDataClass.IDENTITY,
        EgressDataClass.AUTHZ,
        EgressDataClass.CREDENTIAL,
        EgressDataClass.ROW_DETAIL,
    ):
        assert policy.evaluate(data_class).allowed is False


def test_llm_egress_requires_k_anonymity_evidence_for_aggregate_results() -> None:
    policy = LLMEgressPolicy(k_anonymity=5)
    assert policy.evaluate(EgressDataClass.AGGREGATE_RESULT).allowed is False
    assert policy.evaluate(EgressDataClass.AGGREGATE_RESULT, min_entity_count=4).allowed is False
    assert policy.evaluate(EgressDataClass.AGGREGATE_RESULT, min_entity_count=5).allowed is True


def test_llm_egress_fails_closed_when_payload_contains_pii() -> None:
    policy = LLMEgressPolicy()
    decision = policy.evaluate(EgressDataClass.SQL, contains_pii=True)
    assert decision.allowed is False
