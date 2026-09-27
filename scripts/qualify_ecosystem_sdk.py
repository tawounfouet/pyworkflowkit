"""M52 ecosystem SDK artifact conformance."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

CONFORMANCE_PROGRAM = r"""
import json
import sys

from pyworkflowkit import WorkflowRuntime, workflow
from pyworkflowkit.ecosystem import (
    ECOSYSTEM_SDK_CONTRACT_VERSION,
    PluginCatalog,
    PluginDiscovery,
    PluginDiscoveryStatus,
    PluginType,
    assert_plugin_conforms,
    ecosystem_contract_snapshot,
    external_workload_task,
)

scenario = sys.argv[1]
name = "ecosystem-template"

if scenario == "present":
    discovery = PluginDiscovery()
    candidates = discovery.discover(plugin_types=(PluginType.WORKLOAD,))
    candidate = next(
        item
        for item in candidates
        if item.plugin_type is PluginType.WORKLOAD and item.name == name
    )

    loaded = candidate.entry_point.load()
    registration = loaded() if callable(loaded) else loaded
    report = assert_plugin_conforms(
        registration,
        entry_point_name=name,
        plugin_type=PluginType.WORKLOAD,
    )
    assert report.compatible

    catalog = PluginCatalog()
    enabled = discovery.enable_selected(
        catalog=catalog,
        enabled={PluginType.WORKLOAD: {name}},
    )
    result = next(
        item
        for item in enabled.results
        if item.plugin.plugin_type is PluginType.WORKLOAD and item.plugin.name == name
    )
    assert result.status is PluginDiscoveryStatus.LOADED

    workload = catalog.workloads.create(name)
    handle = external_workload_task(
        id="external",
        provider="ecosystem-template",
        workload_ref="reference",
        workload=workload,
    )

    @workflow(id="ecosystem.template.conformance", version="1")
    def definition():
        return (handle,)

    runtime = WorkflowRuntime()
    runtime.register(handle.handler_ref, handle.handler)
    built = definition.build()
    run = runtime.run(built)
    manifest = runtime.manifest(built, run.run_id)

    assert run.status.value == "SUCCEEDED"
    external_ref = manifest.tasks[0].external_refs[0]
    assert external_ref.provider == "ecosystem-template"
    assert external_ref.external_run_id.startswith("template-")

    snapshot = ecosystem_contract_snapshot()
    assert snapshot["sdk_contract_version"] == ECOSYSTEM_SDK_CONTRACT_VERSION == "1"
    assert snapshot["compatibility"] == {
        "series": "0.8-0.9",
        "minimum": "0.8.0b1",
        "maximum_exclusive": "1.0",
    }
    assert snapshot["supported_python_versions"] == ["3.11", "3.12", "3.13"]
    assert snapshot["contracts"] == {
        "control_plane": "1",
        "external_workload": "1",
        "observability": "1",
        "plugin_api": "1",
        "references": "1",
    }
    assert snapshot["entry_point_groups"] == {
        "event": "pyworkflowkit.events",
        "executor": "pyworkflowkit.executors",
        "metadata": "pyworkflowkit.metadata",
        "workload": "pyworkflowkit.workloads",
    }
    json.dumps(snapshot, allow_nan=False, sort_keys=True)
    print("ecosystem-sdk-conformance: ok")
elif scenario == "absent":
    candidates = PluginDiscovery().discover(plugin_types=(PluginType.WORKLOAD,))
    assert all(item.name != name for item in candidates)

    @workflow(id="ecosystem.core.after-uninstall", version="1")
    def definition():
        from pyworkflowkit import task

        @task(id="core")
        def core():
            return "ok"

        return (core,)

    built = definition.build()
    runtime = WorkflowRuntime()
    for handle in definition.task_handles():
        runtime.register(handle.handler_ref, handle.handler)
    run = runtime.run(built)
    assert run.status.value == "SUCCEEDED"
    print("ecosystem-sdk-uninstall-isolation: ok")
else:
    raise SystemExit(f"unknown scenario: {scenario}")
"""


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
        help="Existing PyWorkflowKit wheel. When omitted, build one from the repository.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    template = root / "ecosystem-template"

    with tempfile.TemporaryDirectory(prefix="pyworkflowkit-m52-") as temp:
        workspace = Path(temp)
        core_dist = workspace / "core-dist"
        template_dist = workspace / "template-dist"
        core_dist.mkdir()
        template_dist.mkdir()

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

        _run(
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(template_dist),
            str(template),
        )
        template_wheel = _single_wheel(template_dist)

        environment = workspace / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        program = workspace / "ecosystem_conformance.py"
        program.write_text(CONFORMANCE_PROGRAM, encoding="utf-8")

        _run(str(python), "-m", "pip", "install", "--upgrade", "pip")
        _run(str(python), "-m", "pip", "install", str(core_wheel))
        _run(str(python), "-m", "pip", "install", "--no-deps", str(template_wheel))
        _run(str(python), str(program), "present", cwd=workspace)
        _run(
            str(python),
            "-m",
            "pip",
            "uninstall",
            "-y",
            "pyworkflowkit-ecosystem-template",
        )
        _run(str(python), str(program), "absent", cwd=workspace)

        snapshot = subprocess.run(
            [
                str(python),
                "-c",
                (
                    "import json;"
                    "from pyworkflowkit.ecosystem import ecosystem_contract_snapshot;"
                    "print(json.dumps(ecosystem_contract_snapshot(),sort_keys=True))"
                ),
            ],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        json.loads(snapshot)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
