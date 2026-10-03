#!/usr/bin/env python3
"""Generate and validate the deterministic PyWorkflowKit 2.0.0rc1 evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib import import_module
from pathlib import Path

import pyworkflowkit
from pyworkflowkit._architecture import V2_CANONICAL_PUBLIC_NAMESPACES
from pyworkflowkit._compat.v1_to_v2 import migration_contract_snapshot
from pyworkflowkit.contracts.v2_release_candidate import (
    V2_RC_PUBLIC_SURFACES,
    V2_RELEASE_CANDIDATE_VERSION,
    v2_release_candidate_contract_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _fixture_evidence(source_root: Path) -> dict[str, str]:
    fixtures: list[Path] = []
    serialization = source_root / "tests" / "fixtures" / "v2_serialization"
    fixtures.extend(sorted(serialization.glob("*.json")))
    fixtures.extend(
        [
            source_root / "tests" / "fixtures" / "v2" / "customer360" / "README.md",
            source_root / "tests" / "fixtures" / "v2" / "migration" / "README.md",
        ]
    )

    missing = [path for path in fixtures if not path.is_file()]
    if missing:
        rendered = ", ".join(str(path.relative_to(source_root)) for path in missing)
        raise SystemExit(f"missing LOT-22 evidence fixtures: {rendered}")

    return {
        str(path.relative_to(source_root)): _sha256(path)
        for path in sorted(fixtures)
    }


def release_evidence_manifest(*, source_root: Path) -> dict[str, object]:
    """Return deterministic RC evidence from the installed package plus source fixtures."""

    if pyworkflowkit.__version__ != V2_RELEASE_CANDIDATE_VERSION:
        raise SystemExit(
            "installed package version does not match V2 RC contract: "
            f"{pyworkflowkit.__version__!r} != {V2_RELEASE_CANDIDATE_VERSION!r}"
        )

    if tuple(pyworkflowkit.__all__) != V2_RC_PUBLIC_SURFACES["pyworkflowkit"]:
        raise SystemExit("installed package root does not match frozen V2 RC surface")

    if set(V2_RC_PUBLIC_SURFACES) != set(V2_CANONICAL_PUBLIC_NAMESPACES):
        raise SystemExit("frozen V2 RC namespaces do not match architecture baseline")

    for module_name, expected in V2_RC_PUBLIC_SURFACES.items():
        module = import_module(module_name)
        if tuple(module.__all__) != expected:
            raise SystemExit(f"public surface drift: {module_name}")

    migration = migration_contract_snapshot()
    if migration["generic_aliases_preserved"] is not False:
        raise SystemExit("V1 migration unexpectedly preserves generic aliases")
    if migration["ambiguous_external_attempt_ownership_invented"] is not False:
        raise SystemExit("V1 migration unexpectedly invents external attempt ownership")

    return {
        "manifest_version": "1",
        "candidate_version": pyworkflowkit.__version__,
        "release_candidate": v2_release_candidate_contract_snapshot(),
        "migration": migration,
        "fixture_sha256": _fixture_evidence(source_root),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="Repository root containing release evidence fixtures.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest = release_evidence_manifest(source_root=args.source_root.resolve())
    rendered = json.dumps(manifest, indent=2, sort_keys=True)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)


if __name__ == "__main__":
    main()
