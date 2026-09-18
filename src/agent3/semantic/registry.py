from __future__ import annotations

from pathlib import Path
import yaml

from agent3.contracts.authz import AuthzContext
from agent3.semantic.models import (
    Additivity,
    DimensionDefinition,
    DimensionValue,
    MandatoryFilter,
    MetricDefinition,
)


class SemanticRegistry:
    def __init__(
        self,
        metrics: tuple[MetricDefinition, ...],
        dimensions: tuple[DimensionDefinition, ...] = (),
    ) -> None:
        self._metrics = {metric.id: metric for metric in metrics}
        self._dimensions = {dimension.id: dimension for dimension in dimensions}

    def get(self, authz: AuthzContext, metric_id: str) -> MetricDefinition | None:
        _ = authz
        return self._metrics.get(metric_id)

    def resolve(self, authz: AuthzContext, phrase: str) -> MetricDefinition | None:
        _ = authz
        folded = phrase.strip().casefold()
        matches = []
        for metric in self._metrics.values():
            if any(folded == x.casefold() for x in (metric.id, metric.name, *metric.aliases)):
                matches.append(metric)
        return matches[0] if len(matches) == 1 else None

    def all(self, authz: AuthzContext) -> tuple[MetricDefinition, ...]:
        _ = authz
        return tuple(self._metrics.values())

    def get_dimension(self, authz: AuthzContext, dimension_id: str) -> DimensionDefinition | None:
        _ = authz
        return self._dimensions.get(dimension_id)

    def all_dimensions(self, authz: AuthzContext) -> tuple[DimensionDefinition, ...]:
        _ = authz
        return tuple(self._dimensions.values())

    def resolve_dimension(self, authz: AuthzContext, phrase: str) -> DimensionDefinition | None:
        _ = authz
        folded = phrase.strip().casefold()
        matches = []
        for dimension in self._dimensions.values():
            names = (dimension.id, dimension.name, dimension.field, *dimension.aliases)
            if any(folded == item.casefold() for item in names):
                matches.append(dimension)
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SemanticRegistry":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        metrics: list[MetricDefinition] = []
        for raw in payload.get("metrics", []):
            additivity = raw.get("additivity") or {}
            metrics.append(MetricDefinition(
                id=raw["id"],
                name=raw["name"],
                aliases=tuple(raw.get("aliases", [])),
                aggregation=raw["aggregation"],
                measure=raw["measure"],
                source_entity=raw["source_entity"],
                mandatory_filters=tuple(MandatoryFilter(field=i["field"], op=i["op"], value=i["value"]) for i in raw.get("mandatory_filters", [])),
                additivity_time=Additivity(additivity.get("time", Additivity.ADDITIVE.value)),
                grain=tuple(raw.get("grain", [])),
                valid_dimensions=tuple(raw.get("valid_dimensions", [])),
                owner=raw.get("owner", ""),
                caveats=raw.get("caveats", ""),
                time_field=raw.get("time_field", "dt"),
            ))

        dimensions: list[DimensionDefinition] = []
        for raw in payload.get("dimensions", []):
            values = tuple(
                DimensionValue(
                    value=str(item["value"]),
                    name=str(item["name"]),
                    aliases=tuple(item.get("aliases", [])),
                )
                for item in raw.get("values", [])
            )
            dimensions.append(DimensionDefinition(
                id=raw["id"],
                name=raw["name"],
                field=raw.get("field", raw["id"]),
                aliases=tuple(raw.get("aliases", [])),
                values=values,
            ))
        return cls(tuple(metrics), tuple(dimensions))
