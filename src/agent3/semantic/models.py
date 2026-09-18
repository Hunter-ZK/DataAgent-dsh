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
class DimensionValue:
    value: str
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DimensionDefinition:
    """Business vocabulary mapped to one physical dimension field."""

    id: str
    name: str
    field: str
    aliases: tuple[str, ...] = ()
    values: tuple[DimensionValue, ...] = ()


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
    time_field: str = "dt"


@dataclass(frozen=True, slots=True)
class QueryIR:
    metric_id: str
    dimensions: tuple[str, ...] = ()
    filters: tuple[MandatoryFilter, ...] = ()
    time_values: tuple[str, ...] = ()
