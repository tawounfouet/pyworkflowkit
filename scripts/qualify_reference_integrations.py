"""Build/install/uninstall qualification for M50 reference integration wheels."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import venv
from dataclasses import dataclass
from pathlib import Path

PYINGESTKIT_REFERENCE = (
    "git+https://github.com/tawounfouet/pyingestkit.git"
    "@a19264845e10769fb8fd8cd42c83193ae011f702"
)


@dataclass(frozen=True, slots=True)
class ReferencePackage:
    directory: str
    distribution: str
    plugin_type: str
    entry_name: str
    scenario: str
    install_pyingestkit: bool = False


PACKAGES = (
    ReferencePackage(
        directory="reference-workload",
        distribution="pyworkflowkit-reference-workload",
        plugin_type="workload",
        entry_name="reference-workload",
        scenario="workload",
    ),
    ReferencePackage(
        directory="reference-event-sink",
        distribution="pyworkflowkit-reference-event-sink",
        plugin_type="event",
        entry_name="reference-event-sink",
        scenario="event",
    ),
    ReferencePackage(
        directory="reference-metadata",
        distribution="pyworkflowkit-reference-metadata",
        plugin_type="metadata",
        entry_name="reference-metadata",
        scenario="metadata",
    ),
    ReferencePackage(
        directory="reference-pyingestkit",
        distribution="pyworkflowkit-reference-pyingestkit",
        plugin_type="workload",
        entry_name="pyingestkit-reference",
        scenario="pyingestkit",
        install_pyingestkit=True,
    ),
)


def _run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def _venv_python(environment: Path) -> Path:
    if sys.platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _single_wheel(directory: Path) -> Path:
    wheels = tuple(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one wheel in {directory}, found {len(wheels)}")
    return wheels[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--core-wheel",
        type=Path,
        help="Existing PyWorkflowKit wheel. When omitted, a wheel is built from the repository.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    integrations = root / "reference-integrations"
    conformance = integrations / "conformance.py"

    with tempfile.TemporaryDirectory(prefix="pyworkflowkit-m50-") as temp:
        workspace = Path(temp)
        core_dist = workspace / "core-dist"
        package_dist = workspace / "integration-dist"
        core_dist.mkdir()
        package_dist.mkdir()

        if args.core_wheel is None:
            _run(
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(core_dist),
                str(root),
            )
            core_wheel = _single_wheel(core_dist)
        else:
            core_wheel = args.core_wheel.resolve()
            if not core_wheel.is_file():
                raise FileNotFoundError(core_wheel)

        built: dict[ReferencePackage, Path] = {}
        for package in PACKAGES:
            destination = package_dist / package.directory
            destination.mkdir()
            _run(
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(destination),
                str(integrations / package.directory),
            )
            built[package] = _single_wheel(destination)

        environment = workspace / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)

        _run(str(python), "-m", "pip", "install", "--upgrade", "pip")
        _run(str(python), "-m", "pip", "install", str(core_wheel))
        _run(str(python), str(conformance), "core")

        for package in PACKAGES:
            if package.install_pyingestkit:
                _run(str(python), "-m", "pip", "install", PYINGESTKIT_REFERENCE)

            _run(
                str(python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                str(built[package]),
            )
            _run(
                str(python),
                str(conformance),
                package.scenario,
                "--plugin-type",
                package.plugin_type,
                "--name",
                package.entry_name,
            )
            _run(
                str(python),
                "-m",
                "pip",
                "uninstall",
                "-y",
                package.distribution,
            )
            _run(
                str(python),
                str(conformance),
                "absent",
                "--plugin-type",
                package.plugin_type,
                "--name",
                package.entry_name,
            )
            _run(str(python), str(conformance), "core")

            if package.install_pyingestkit:
                _run(str(python), "-m", "pip", "uninstall", "-y", "pyingestkit")
                _run(str(python), str(conformance), "core")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
