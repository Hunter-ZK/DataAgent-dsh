from __future__ import annotations

from pathlib import Path
import yaml

from agent3.contracts.authz import AuthzContext
from agent3.semantic.models import Additivity, MandatoryFilter, MetricDefinition


class SemanticRegistry:
    def __init__(self, metrics: tuple[MetricDefinition, ...]) -> None:
        self._metrics = {metric.id: metric for metric in metrics}

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
            ))
        return cls(tuple(metrics))
