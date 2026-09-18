from __future__ import annotations

from pathlib import Path

import yaml

from agent3.metadata.in_memory import InMemoryMetadataProvider
from agent3.metadata.models import ColumnMetadata, TableMetadata


def load_yaml_metadata(path: str | Path) -> InMemoryMetadataProvider:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    tables: list[TableMetadata] = []
    for raw in payload.get("tables", []):
        tables.append(
            TableMetadata(
                full_name=str(raw["full_name"]),
                description=str(raw.get("description", "")),
                aliases=tuple(str(item) for item in raw.get("aliases", [])),
                partition_fields=tuple(str(item) for item in raw.get("partition_fields", [])),
                row_count_estimate=raw.get("row_count_estimate"),
                columns=tuple(
                    ColumnMetadata(
                        name=str(column["name"]),
                        data_type=str(column["data_type"]),
                        description=str(column.get("description", "")),
                        nullable=bool(column.get("nullable", True)),
                        sensitive=bool(column.get("sensitive", False)),
                    )
                    for column in raw.get("columns", [])
                ),
            )
        )
    if not tables:
        raise ValueError("metadata YAML must contain at least one table")
    return InMemoryMetadataProvider(tuple(tables))
