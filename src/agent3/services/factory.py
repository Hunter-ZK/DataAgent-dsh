from pathlib import Path

from agent3.metadata.demo import build_demo_metadata
from agent3.metadata.yaml_provider import load_yaml_metadata
from agent3.semantic.registry import SemanticRegistry
from agent3.services.core import Agent3Core


def build_demo_core() -> Agent3Core:
    root = Path(__file__).resolve().parents[3]
    semantics = SemanticRegistry.from_yaml(root / "semantic_models" / "loan.yaml")
    return Agent3Core(metadata=build_demo_metadata(), semantics=semantics)


def build_core_from_files(*, metadata_yaml: str | Path, semantic_yaml: str | Path) -> Agent3Core:
    metadata = load_yaml_metadata(metadata_yaml)
    semantics = SemanticRegistry.from_yaml(semantic_yaml)
    return Agent3Core(metadata=metadata, semantics=semantics)
