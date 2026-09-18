from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "src" / "agent3"
PLATFORM_SRC = ROOT / "src" / "agent3_api"
FORBIDDEN_CORE_PREFIXES = ("agent3.adapters", "agent3_api", "fastapi", "mcp", "deepseek_harness")
FORBIDDEN_ADAPTER_IMPORTS = ("sqlglot", "duckdb")


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def main() -> None:
    errors: list[str] = []
    for path in CORE_SRC.rglob("*.py"):
        rel = path.relative_to(CORE_SRC)
        imports = imported_modules(path)
        if rel.parts and rel.parts[0] == "adapters":
            for module in imports:
                if module.startswith(FORBIDDEN_ADAPTER_IMPORTS):
                    errors.append(f"adapter contains domain/runtime logic import: {rel}: {module}")
            continue
        for module in imports:
            if module.startswith(FORBIDDEN_CORE_PREFIXES):
                errors.append(f"core depends on adapter/framework: {rel}: {module}")

    # Platform code may depend on Core/frameworks, but Core must remain unaware of it.
    if not PLATFORM_SRC.exists():
        errors.append("platform package src/agent3_api is missing")

    if errors:
        raise SystemExit("\n".join(errors))
    print("architecture boundaries: OK")


if __name__ == "__main__":
    main()
