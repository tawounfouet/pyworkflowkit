"""Architectural boundary tests enforcing zero unshielded core dependencies on OpenTelemetry."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src" / "pyworkflowkit"


def _module_name(path: Path) -> str:
    relative = path.relative_to(ROOT / "src").with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def test_core_runtime_never_has_top_level_opentelemetry_import() -> None:
    """No module in pyworkflowkit should import opentelemetry at module top-level."""
    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("opentelemetry"), (
                        f"Module '{_module_name(path)}' has forbidden "
                        f"top-level import of '{alias.name}'"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith("opentelemetry"), (
                    f"Module '{_module_name(path)}' has forbidden "
                    f"top-level import from '{node.module}'"
                )


def test_opentelemetry_imports_isolated_strictly_to_telemetry_module() -> None:
    """Any deferred import of opentelemetry must be restricted strictly to telemetry.py."""
    allowed_file = (SOURCE_ROOT / "runtime" / "telemetry.py").resolve()
    for path in SOURCE_ROOT.rglob("*.py"):
        if path.resolve() == allowed_file:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("opentelemetry"), (
                        f"Module '{_module_name(path)}' imports '{alias.name}' outside telemetry.py"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith("opentelemetry"), (
                    f"Module '{_module_name(path)}' imports from "
                    f"'{node.module}' outside telemetry.py"
                )
