#!/usr/bin/env python3
"""Verify source-tree release metadata before artifact qualification."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["version"])


def verify_release_metadata(*, tag: str | None = None) -> dict[str, str]:
    version = project_version()
    release_note = ROOT / "docs" / "releases" / f"{version}.md"
    changelog = ROOT / "CHANGELOG.md"

    if not release_note.is_file():
        raise SystemExit(f"missing release note: {release_note.relative_to(ROOT)}")

    lines = [
        line.strip()
        for line in release_note.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected_heading = f"# PyWorkflowKit {version}"
    if not lines or lines[0] != expected_heading:
        raise SystemExit(
            f"release note must start with {expected_heading!r}: "
            f"{release_note.relative_to(ROOT)}"
        )

    changelog_text = changelog.read_text(encoding="utf-8")
    if version not in changelog_text:
        raise SystemExit(f"CHANGELOG.md does not mention package version {version}")

    expected_tag = f"v{version}"
    if tag is not None and tag != expected_tag:
        raise SystemExit(f"tag {tag!r} does not match package version tag {expected_tag!r}")

    return {
        "version": version,
        "release_note": str(release_note.relative_to(ROOT)),
        "expected_tag": expected_tag,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--print-version", action="store_true")
    args = parser.parse_args()

    result = verify_release_metadata(tag=args.tag)
    if args.print_version:
        print(result["version"])
        return
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
