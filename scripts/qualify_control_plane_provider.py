"""Artifact-level conformance for the M51 control-plane provider boundary."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

CONFORMANCE_PROGRAM = r"""
import json

from pyworkflowkit._compat.v1_root import WorkflowRuntime
from pyworkflowkit.control_plane import (
    CONTROL_PLANE_PROVIDER_CONTRACT_VERSION,
    ControlPlaneCapabilityError,
    ControlPlaneProvider,
    WorkflowRuntimeProvider,
)

runtime = WorkflowRuntime()
runtime.register("provider.fetch", lambda: {"rows": 3})
runtime.register("provider.publish", lambda: "published")

workflow = {
    "workflow_id": "conformance.control-plane",
    "version": "1",
    "tasks": [
        {"task_id": "fetch", "handler_ref": "provider.fetch"},
        {
            "task_id": "publish",
            "handler_ref": "provider.publish",
            "depends_on": ["fetch"],
        },
    ],
    "parameters": [
        {
            "name": "api_token",
            "required": False,
            "default": None,
            "sensitive": True,
        }
    ],
}

provider = WorkflowRuntimeProvider(runtime)
assert isinstance(provider, ControlPlaneProvider)
assert CONTROL_PLANE_PROVIDER_CONTRACT_VERSION == "1"

capabilities = provider.inspect_capabilities()
assert capabilities.operations["execute_workflow"] is True
assert capabilities.operations["request_cancellation"] is False
assert capabilities.scheduling_owned_by_control_plane is True
assert capabilities.background_execution is False

validation = provider.validate_workflow(workflow)
assert validation.valid is True

inspection = provider.inspect_workflow(workflow)
assert inspection.task_order == ("fetch", "publish")
assert tuple(group.task_ids for group in inspection.groups) == (("fetch",), ("publish",))

run = provider.execute_workflow(
    workflow,
    parameters={"api_token": "must-not-leak"},
)
assert run.status == "SUCCEEDED"
assert "parameters" not in run.model_dump()

inspected = provider.inspect_run(run.run_id)
assert inspected == run

events = provider.list_runtime_events(run.run_id)
assert events
assert [event.event_sequence for event in events] == sorted(
    event.event_sequence for event in events
)

manifest = provider.retrieve_manifest(workflow, run.run_id)
assert manifest["schema_version"] == "1"
assert manifest["parameters"]["api_token"] == "<redacted>"

lineage = provider.retrieve_lineage(workflow, run.run_id)
assert tuple(task.task_id for task in lineage.tasks) == ("fetch", "publish")
assert len(lineage.dependencies) == 1

recovery = provider.assess_recovery(run.run_id)
assert recovery.workflow_status == "SUCCEEDED"
assert recovery.liveness == "terminal"
assert recovery.resume_eligibility == "not_eligible"

try:
    provider.request_cancellation(run.run_id, reason="conformance")
except ControlPlaneCapabilityError as exc:
    assert exc.operation == "request_cancellation"
else:
    raise AssertionError("request_cancellation should be unsupported")

payload = {
    "capabilities": capabilities.model_dump(mode="json"),
    "validation": validation.model_dump(mode="json"),
    "inspection": inspection.model_dump(mode="json"),
    "run": run.model_dump(mode="json"),
    "events": [event.model_dump(mode="json") for event in events],
    "manifest": manifest,
    "lineage": lineage.model_dump(mode="json"),
    "recovery": recovery.model_dump(mode="json"),
}
json.dumps(payload, allow_nan=False, sort_keys=True)
print("control-plane-provider-conformance: ok")
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

    with tempfile.TemporaryDirectory(prefix="pyworkflowkit-m51-") as temp:
        workspace = Path(temp)
        dist = workspace / "dist"
        dist.mkdir()

        if args.core_wheel is None:
            _run(
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(dist),
                str(root),
            )
            core_wheel = _single_wheel(dist)
        else:
            core_wheel = args.core_wheel.resolve()
            if not core_wheel.is_file():
                raise FileNotFoundError(core_wheel)

        environment = workspace / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        program = workspace / "control_plane_conformance.py"
        program.write_text(CONFORMANCE_PROGRAM, encoding="utf-8")

        _run(str(python), "-m", "pip", "install", "--upgrade", "pip")
        _run(str(python), "-m", "pip", "install", str(core_wheel))
        _run(str(python), str(program), cwd=workspace)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
