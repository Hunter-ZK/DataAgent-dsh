from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Additivity(StrEnum):
    ADDITIVE = "additive"
    NON_ADDITIVE = "non_additive"


@dataclass(frozen=True, slots=True)
class MandatoryFilter:
    field: str
    op: str
    value: Any


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    id: str
    name: str
    aggregation: str
    measure: str
    source_entity: str
    aliases: tuple[str, ...] = ()
    mandatory_filters: tuple[MandatoryFilter, ...] = ()
    additivity_time: Additivity = Additivity.ADDITIVE
    grain: tuple[str, ...] = ()
    valid_dimensions: tuple[str, ...] = ()
    owner: str = ""
    caveats: str = ""


@dataclass(frozen=True, slots=True)
class QueryIR:
    metric_id: str
    dimensions: tuple[str, ...] = ()
    filters: tuple[MandatoryFilter, ...] = ()
    time_values: tuple[str, ...] = ()
