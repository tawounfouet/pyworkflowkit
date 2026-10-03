"""LOT-00 architecture baseline and migration-boundary tests."""

from __future__ import annotations

import ast
import json
from importlib import import_module
from pathlib import Path

import pyworkflowkit
from pyworkflowkit._architecture import (
    V2_CANONICAL_PUBLIC_NAMESPACES,
    V2_LEGACY_FACADES,
    V2_NAMESPACE_TIERS,
    V2_OPTIONAL_SIBLING_IMPORT_OWNERS,
    V2_ROOT_TARGET_ALLOWLIST,
    V2_TARGET_RELEASE,
    StabilityTier,
    v2_architecture_snapshot,
)
from pyworkflowkit.public_api import (
    PUBLIC_API_SURFACES,
    v2_public_api_baseline_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src" / "pyworkflowkit"

TRANSITIONAL_V2_NAMESPACES = (
    "pyworkflowkit.authoring",
    "pyworkflowkit.planning",
    "pyworkflowkit.runtime",
    "pyworkflowkit.states",
    "pyworkflowkit.policies",
    "pyworkflowkit.executors",
    "pyworkflowkit.persistence",
    "pyworkflowkit.serialization",
    "pyworkflowkit.lineage",
    "pyworkflowkit.diagnostics",
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


def test_v2_architecture_snapshot_is_deterministic_and_json_serializable() -> None:
    snapshot = v2_architecture_snapshot()

    assert snapshot["contract_version"] == "1"
    assert snapshot["target_release"] == "2.0.0"
    assert json.loads(json.dumps(snapshot, sort_keys=True)) == snapshot


def test_v2_public_api_baseline_wraps_architecture_without_mutating_v1_freeze() -> None:
    snapshot = v2_public_api_baseline_snapshot()

    assert snapshot["contract_version"] == "1"
    assert snapshot["target_release"] == V2_TARGET_RELEASE
    assert snapshot["architecture"] == v2_architecture_snapshot()

    # LOT-00 is additive: the stable 1.1 root facade remains unchanged until
    # later lots deliberately replace the root contract.
    assert set(pyworkflowkit.__all__) == set(PUBLIC_API_SURFACES["pyworkflowkit"])


def test_v2_semantic_namespaces_are_importable_and_explicit() -> None:
    for module_name in TRANSITIONAL_V2_NAMESPACES:
        module = import_module(module_name)
        exported = tuple(module.__all__)

        assert len(exported) == len(set(exported)), module_name
        assert all(not name.startswith("_") for name in exported), module_name
        for symbol in exported:
            assert hasattr(module, symbol), f"{module_name}.{symbol}"


def test_v2_namespace_classification_is_explicit() -> None:
    assert set(V2_CANONICAL_PUBLIC_NAMESPACES).issubset(V2_NAMESPACE_TIERS)
    assert V2_NAMESPACE_TIERS["pyworkflowkit.control_plane"] is StabilityTier.PROVISIONAL
    assert V2_NAMESPACE_TIERS["pyworkflowkit.ecosystem"] is StabilityTier.COMPATIBILITY
    assert "pyworkflowkit.ecosystem" in V2_LEGACY_FACADES
    assert "pyworkflowkit.ecosystem" not in V2_CANONICAL_PUBLIC_NAMESPACES


def test_v2_root_target_is_narrower_than_legacy_root() -> None:
    legacy_root = set(PUBLIC_API_SURFACES["pyworkflowkit"])
    target_root = set(V2_ROOT_TARGET_ALLOWLIST)

    assert "RunContext" in legacy_root
    assert "RunContext" not in target_root
    assert "TaskResult" in legacy_root
    assert "TaskResult" not in target_root
    assert "WorkflowResult" in target_root
    assert "TimeoutPolicy" in target_root


def test_sibling_framework_imports_are_confined_to_declared_integration_owners() -> None:
    for path in SOURCE_ROOT.rglob("*.py"):
        source_module = _module_name(path)
        for imported in _imported_modules(path):
            for sibling, allowed_owners in V2_OPTIONAL_SIBLING_IMPORT_OWNERS.items():
                if imported != sibling and not imported.startswith(f"{sibling}."):
                    continue
                assert any(
                    source_module == owner or source_module.startswith(f"{owner}.")
                    for owner in allowed_owners
                ), f"{source_module} imports optional sibling {imported}"


def test_canonical_v2_facades_do_not_depend_on_compatibility_layer() -> None:
    roots = {
        namespace.removeprefix("pyworkflowkit.").split(".", maxsplit=1)[0]
        for namespace in TRANSITIONAL_V2_NAMESPACES
    }
    for root in roots:
        package_root = SOURCE_ROOT / root
        for path in package_root.rglob("*.py"):
            imported = _imported_modules(path)
            assert not any(
                name == "pyworkflowkit._compat" or name.startswith("pyworkflowkit._compat.")
                for name in imported
            ), f"{_module_name(path)} depends on V1 compatibility code"



def test_lot15_keeps_pydantic_out_of_canonical_domain_models() -> None:
    domain_files = (
        SOURCE_ROOT / "runtime" / "context.py",
        SOURCE_ROOT / "runtime" / "references.py",
        SOURCE_ROOT / "runtime" / "evidence.py",
        SOURCE_ROOT / "diagnostics" / "failure.py",
        SOURCE_ROOT / "diagnostics" / "model.py",
        SOURCE_ROOT / "lineage" / "model.py",
    )

    for path in domain_files:
        imported = _imported_modules(path)
        assert not any(
            name == "pydantic" or name.startswith("pydantic.")
            for name in imported
        ), f"{_module_name(path)} leaks Pydantic into the canonical domain"
