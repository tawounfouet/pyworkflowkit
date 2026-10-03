"""Architectural boundary tests enforcing strict separation between Core and CLI."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src" / "pyworkflowkit"

# Subsystems that are part of the CLI/rendering adapter surface
CLI_ADAPTER_PREFIXES = (
    "pyworkflowkit.cli",
    "pyworkflowkit.cli_rendering",
    "pyworkflowkit.cli_contract",
)


def _module_name(path: Path) -> str:
    relative = path.relative_to(ROOT / "src").with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imported_modules(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    return tuple(names)


def test_core_runtime_never_imports_typer_or_rich() -> None:
    """Core runtime modules must never depend on Typer or Rich directly."""
    for path in SOURCE_ROOT.rglob("*.py"):
        module = _module_name(path)
        if any(
            module == prefix or module.startswith(f"{prefix}.") for prefix in CLI_ADAPTER_PREFIXES
        ):
            continue

        imported = _imported_modules(path)
        for imp in imported:
            assert imp != "typer" and not imp.startswith("typer."), (
                f"Core module '{module}' illicitly imports '{imp}'"
            )
            assert imp != "rich" and not imp.startswith("rich."), (
                f"Core module '{module}' illicitly imports '{imp}'"
            )


def test_core_runtime_never_imports_cli_package() -> None:
    """Core domain, engine and persistence must never import pyworkflowkit.cli."""
    for path in SOURCE_ROOT.rglob("*.py"):
        module = _module_name(path)
        if any(
            module == prefix or module.startswith(f"{prefix}.") for prefix in CLI_ADAPTER_PREFIXES
        ):
            continue

        imported = _imported_modules(path)
        for imp in imported:
            assert imp != "pyworkflowkit.cli" and not imp.startswith("pyworkflowkit.cli."), (
                f"Core module '{module}' illicitly imports CLI layer '{imp}'"
            )
