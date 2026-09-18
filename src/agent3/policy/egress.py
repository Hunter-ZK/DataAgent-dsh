from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EgressDataClass(StrEnum):
    SCHEMA = "schema"
    SEMANTIC = "semantic"
    SQL = "sql"
    EVIDENCE = "evidence"
    AGGREGATE_RESULT = "aggregate_result"
    ROW_DETAIL = "row_detail"
    IDENTITY = "identity"
    AUTHZ = "authz"
    CREDENTIAL = "credential"


@dataclass(frozen=True, slots=True)
class EgressDecision:
    allowed: bool
    reason: str


class LLMEgressPolicy:
    """Fail-closed contract for payloads sent to an external LLM.

    The policy does not try to infer PII from arbitrary text. Upstream metadata
    classification must state whether PII is present. Aggregate results also
    need a minimum contributing-entity count supplied by the query/execution
    layer; if that evidence is missing the result is not model-visible.
    """

    def __init__(self, *, k_anonymity: int = 5) -> None:
        if k_anonymity < 1:
            raise ValueError("k_anonymity must be >= 1")
        self.k_anonymity = k_anonymity

    def evaluate(
        self,
        data_class: EgressDataClass,
        *,
        contains_pii: bool = False,
        min_entity_count: int | None = None,
    ) -> EgressDecision:
        if data_class in {EgressDataClass.IDENTITY, EgressDataClass.AUTHZ, EgressDataClass.CREDENTIAL}:
            return EgressDecision(False, f"{data_class.value} is never model-visible")
        if data_class is EgressDataClass.ROW_DETAIL:
            return EgressDecision(False, "row-level detail is not model-visible")
        if contains_pii:
            return EgressDecision(False, "payload contains PII")
        if data_class is EgressDataClass.AGGREGATE_RESULT:
            if min_entity_count is None:
                return EgressDecision(False, "aggregate result lacks contributing-entity evidence")
            if min_entity_count < self.k_anonymity:
                return EgressDecision(
                    False,
                    f"aggregate result violates k-anonymity threshold {self.k_anonymity}",
                )
        return EgressDecision(True, "allowed by LLM egress contract")
