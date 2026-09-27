"""Qualify PyWorkflowKit wheel/sdist packaging and distribution invariants."""

from __future__ import annotations

import argparse
import configparser
import json
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from pyworkflowkit.contracts.distribution import (
    BUILD_BACKEND_REQUIREMENT,
    CONSOLE_SCRIPTS,
    FORBIDDEN_SDIST_PREFIXES,
    FORBIDDEN_WHEEL_PREFIXES,
    OPTIONAL_EXTRA_NAMES,
    PACKAGE_NAME,
    PYTHON_REQUIRES,
    REQUIRED_PROJECT_URL_NAMES,
    REQUIRED_SDIST_PATHS,
    REQUIRED_WHEEL_PATHS,
    RUNTIME_DEPENDENCY_RANGES,
)

ROOT = Path(__file__).resolve().parents[1]


def _project() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _canonical_requirement(value: str) -> str:
    requirement = Requirement(value)
    return (
        f"{canonicalize_name(requirement.name)}"
        f"{requirement.specifier}"
        f"{'; ' + str(requirement.marker) if requirement.marker else ''}"
    )


def _dist_info_member(names: set[str], suffix: str) -> str:
    matches = sorted(name for name in names if name.endswith(f".dist-info/{suffix}"))
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one dist-info/{suffix}, got {matches}")
    return matches[0]


def _metadata_from_wheel(wheel: Path) -> tuple[Any, set[str], str]:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_path = _dist_info_member(names, "METADATA")
        wheel_path = _dist_info_member(names, "WHEEL")
        entry_points_path = _dist_info_member(names, "entry_points.txt")
        metadata = BytesParser().parsebytes(archive.read(metadata_path))
        wheel_text = archive.read(wheel_path).decode("utf-8")
        entry_points = archive.read(entry_points_path).decode("utf-8")
    return metadata, names, wheel_text + "\n" + entry_points


def _entry_points_from_wheel(wheel: Path) -> dict[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        path = _dist_info_member(names, "entry_points.txt")
        parser = configparser.ConfigParser()
        parser.read_string(archive.read(path).decode("utf-8"))
    return dict(parser["console_scripts"])


def _project_urls(metadata: Any) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in metadata.get_all("Project-URL", []):
        label, url = raw.split(",", maxsplit=1)
        values[label.strip()] = url.strip()
    return values


def _runtime_requires(metadata: Any) -> set[str]:
    values: set[str] = set()
    for raw in metadata.get_all("Requires-Dist", []):
        requirement = Requirement(raw)
        if requirement.marker is not None and "extra ==" in str(requirement.marker):
            continue
        values.add(_canonical_requirement(raw))
    return values


def _wheel_package_paths(names: set[str]) -> set[str]:
    return {name for name in names if name.startswith("pyworkflowkit/") and not name.endswith("/")}


def _qualify_source_metadata(project_data: dict[str, Any]) -> dict[str, object]:
    build_requires = tuple(project_data["build-system"]["requires"])
    project = project_data["project"]

    assert build_requires == (BUILD_BACKEND_REQUIREMENT,)
    assert canonicalize_name(project["name"]) == PACKAGE_NAME
    assert project["requires-python"] == PYTHON_REQUIRES
    assert tuple(project["dependencies"]) == RUNTIME_DEPENDENCY_RANGES
    assert tuple(sorted(project["optional-dependencies"])) == OPTIONAL_EXTRA_NAMES
    assert dict(project["scripts"]) == dict(CONSOLE_SCRIPTS)

    urls = project["urls"]
    assert set(REQUIRED_PROJECT_URL_NAMES) <= set(urls)

    readme = str(project["readme"])
    assert readme == "README.md"
    readme_text = (ROOT / readme).read_text(encoding="utf-8")
    assert "](docs/" not in readme_text
    assert "](examples/" not in readme_text

    return {
        "version": str(project["version"]),
        "build_backend": build_requires[0],
        "extras": sorted(project["optional-dependencies"]),
        "project_urls": sorted(urls),
    }


def _qualify_wheel(wheel: Path, *, expected_version: str) -> dict[str, object]:
    metadata, names, combined = _metadata_from_wheel(wheel)

    assert canonicalize_name(metadata["Name"]) == PACKAGE_NAME
    assert metadata["Version"] == expected_version
    assert metadata["Requires-Python"] == PYTHON_REQUIRES
    assert metadata["Summary"] == "Reliable workflows without running a workflow platform."
    assert metadata["Description-Content-Type"].startswith("text/markdown")

    expected_runtime = {_canonical_requirement(value) for value in RUNTIME_DEPENDENCY_RANGES}
    assert _runtime_requires(metadata) == expected_runtime
    assert set(metadata.get_all("Provides-Extra", [])) == set(OPTIONAL_EXTRA_NAMES)
    assert set(REQUIRED_PROJECT_URL_NAMES) <= set(_project_urls(metadata))

    assert _entry_points_from_wheel(wheel) == dict(CONSOLE_SCRIPTS)

    for path in REQUIRED_WHEEL_PATHS:
        assert path in names, path
    for path in names:
        assert not any(path.startswith(prefix) for prefix in FORBIDDEN_WHEEL_PREFIXES), path

    top_level = {path.split("/", maxsplit=1)[0] for path in names if "/" in path}
    assert "pyworkflowkit" in top_level
    assert all(value == "pyworkflowkit" or value.endswith(".dist-info") for value in top_level)

    assert "Root-Is-Purelib: true" in combined
    assert "Tag: py3-none-any" in combined
    assert wheel.name.endswith("-py3-none-any.whl")

    return {
        "filename": wheel.name,
        "file_count": len(names),
        "package_file_count": len(_wheel_package_paths(names)),
        "pure_python": True,
    }


def _sdist_relative_paths(sdist: Path, *, expected_version: str) -> set[str]:
    expected_root = f"{PACKAGE_NAME}-{expected_version}/"
    with tarfile.open(sdist, "r:gz") as archive:
        names = {member.name for member in archive.getmembers() if member.isfile()}

    roots = {name.split("/", maxsplit=1)[0] for name in names}
    assert roots == {expected_root.rstrip("/")}

    return {name[len(expected_root) :] for name in names if name.startswith(expected_root)}


def _qualify_sdist(sdist: Path, *, expected_version: str) -> dict[str, object]:
    paths = _sdist_relative_paths(sdist, expected_version=expected_version)

    for path in REQUIRED_SDIST_PATHS:
        assert path in paths, path
    for path in paths:
        assert not any(path.startswith(prefix) for prefix in FORBIDDEN_SDIST_PREFIXES), path

    allowed_root_files = {
        ".gitignore",
        "CHANGELOG.md",
        "PKG-INFO",
        "README.md",
        "SECURITY.md",
        "pyproject.toml",
    }
    for path in paths:
        assert path in allowed_root_files or path.startswith("src/pyworkflowkit/"), path

    return {
        "filename": sdist.name,
        "file_count": len(paths),
    }


def _compare_wheels(primary: Path, rebuilt: Path) -> dict[str, object]:
    (
        primary_metadata,
        primary_names,
        _,
    ) = _metadata_from_wheel(primary)
    (
        rebuilt_metadata,
        rebuilt_names,
        _,
    ) = _metadata_from_wheel(rebuilt)

    assert primary_metadata["Name"] == rebuilt_metadata["Name"]
    assert primary_metadata["Version"] == rebuilt_metadata["Version"]
    assert primary_metadata["Requires-Python"] == rebuilt_metadata["Requires-Python"]
    assert primary_metadata.get_all("Requires-Dist", []) == rebuilt_metadata.get_all(
        "Requires-Dist", []
    )
    assert _entry_points_from_wheel(primary) == _entry_points_from_wheel(rebuilt)
    assert _wheel_package_paths(primary_names) == _wheel_package_paths(rebuilt_names)

    return {
        "rebuilt_filename": rebuilt.name,
        "package_paths_equal": True,
        "metadata_equal": True,
    }


def qualify_distribution(
    *,
    dist_dir: Path,
    rebuilt_wheel: Path | None = None,
) -> dict[str, object]:
    project_data = _project()
    source = _qualify_source_metadata(project_data)
    version = str(source["version"])

    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    assert len(wheels) == 1, wheels
    assert len(sdists) == 1, sdists

    payload: dict[str, object] = {
        "source": source,
        "wheel": _qualify_wheel(wheels[0], expected_version=version),
        "sdist": _qualify_sdist(sdists[0], expected_version=version),
    }

    if rebuilt_wheel is not None:
        payload["rebuilt"] = _compare_wheels(wheels[0], rebuilt_wheel)

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--rebuilt-wheel", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = qualify_distribution(
        dist_dir=args.dist_dir.resolve(),
        rebuilt_wheel=args.rebuilt_wheel.resolve() if args.rebuilt_wheel else None,
    )

    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print("RQ-05 packaging and distribution qualification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
