"""Transverse qualification for the complete PyWorkflowKit 0.8 interoperability line."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PYINGESTKIT_REFERENCE = (
    "git+https://github.com/tawounfouet/pyingestkit.git@a19264845e10769fb8fd8cd42c83193ae011f702"
)

CONFORMANCE_PROGRAM = r"""
from __future__ import annotations

import tempfile
from pathlib import Path

from pyworkflowkit import (
    TaskDefinition,
    TaskId,
    TaskResult,
    WorkflowDefinition,
    WorkflowId,
    WorkflowRuntime,
    task,
    workflow,
)
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.control_plane import WorkflowRuntimeProvider
from pyworkflowkit.ecosystem import (
    PluginCatalog,
    PluginDiscovery,
    PluginDiscoveryStatus,
    PluginType,
    assert_plugin_conforms,
    ecosystem_contract_snapshot,
    external_workload_task,
)
from pyworkflowkit.plugins import RegisteredPlugin


def registration_for(plugin_type: PluginType, name: str) -> RegisteredPlugin[object]:
    discovery = PluginDiscovery()
    candidates = discovery.discover(plugin_types=(plugin_type,))
    candidate = next(
        item
        for item in candidates
        if item.plugin_type is plugin_type and item.name == name
    )
    loaded = candidate.entry_point.load()
    registration = loaded() if callable(loaded) else loaded
    assert isinstance(registration, RegisteredPlugin)
    return registration


def enable(plugin_type: PluginType, name: str) -> PluginCatalog:
    catalog = PluginCatalog()
    report = PluginDiscovery().enable_selected(
        catalog=catalog,
        enabled={plugin_type: {name}},
    )
    result = next(
        item
        for item in report.results
        if item.plugin.plugin_type is plugin_type and item.plugin.name == name
    )
    assert result.status is PluginDiscoveryStatus.LOADED, result.error
    return catalog


def core_smoke(workflow_id: str) -> None:
    @task(id="core")
    def core() -> TaskResult:
        return TaskResult(output="core-ok")

    @workflow(id=workflow_id, version="1")
    def definition():
        return (core,)

    runtime = WorkflowRuntime()
    runtime.register(core.handler_ref, core.handler)
    built = definition.build()
    run = runtime.run(built)
    manifest = runtime.manifest(built, run.run_id)

    assert run.status.value == "SUCCEEDED"
    assert manifest.tasks[0].status == "SUCCEEDED"


# A. PyWorkflowKit-only local workflow.
core_smoke("qualification.v0_8.a_core")
print("A core-only local workflow: ok")


# B. Third-party executor plugin discovered, conformed and used by the core Runner.
executor_registration = registration_for(PluginType.EXECUTOR, "reference-executor")
assert_plugin_conforms(
    executor_registration,
    entry_point_name="reference-executor",
    plugin_type=PluginType.EXECUTOR,
)
executor_catalog = enable(PluginType.EXECUTOR, "reference-executor")
executor = executor_catalog.executors.create("reference-executor")

handlers = HandlerRegistry()
handlers.register(
    "qualification.executor",
    lambda context: TaskResult(output={"executor": context.task_id}),
)
executor_workflow = WorkflowDefinition(
    workflow_id=WorkflowId("qualification.v0_8.b_executor"),
    version="1",
    tasks=(
        TaskDefinition(
            task_id=TaskId("third-party"),
            handler_ref="qualification.executor",
            executor_key="reference-executor",
        ),
    ),
)
executor_runner = Runner(
    metadata_store=MemoryMetadataStore(),
    handler_registry=handlers,
    executor=executor,
    clock=SystemClock(),
    id_factory=UuidRuntimeIdFactory(),
    sleeper=SystemSleeper(),
)
executor_run = executor_runner.run(executor_workflow)
assert executor_run.status.value == "SUCCEEDED"
print("B third-party executor plugin: ok")


# C. Real PyIngestKit specialized runtime remains one atomic external workload.
from pyingestkit import Job, Pipeline, Runner as PyIngestKitRunner, Step
from pyingestkit.artifacts import LocalArtifactStore

pyingest_registration = registration_for(PluginType.WORKLOAD, "pyingestkit-reference")
assert_plugin_conforms(
    pyingest_registration,
    entry_point_name="pyingestkit-reference",
    plugin_type=PluginType.WORKLOAD,
)
pyingest_catalog = enable(PluginType.WORKLOAD, "pyingestkit-reference")
adapter_factory = pyingest_catalog.workloads.create("pyingestkit-reference")


class QualificationStep(Step):
    def execute(self, context, data):
        del context, data
        return {"rows": 3, "dataset": "customers"}


class QualificationJob(Job):
    id = "qualification.customers"
    version = "1.0.0"

    def pipeline(self) -> Pipeline:
        return Pipeline((QualificationStep(),))


with tempfile.TemporaryDirectory(prefix="qualification-pyingestkit-") as directory:
    external_runner = PyIngestKitRunner(LocalArtifactStore(Path(directory)))
    external_workload = adapter_factory.wrap(
        runner=external_runner,
        job=QualificationJob(),
    )

    external_handle = external_workload_task(
        id="ingest",
        provider="pyingestkit",
        workload_ref="qualification.customers",
        workload=external_workload,
    )

    @workflow(id="qualification.v0_8.c_pyingestkit", version="1")
    def external_definition():
        return (external_handle,)

    external_runtime = WorkflowRuntime()
    external_runtime.register(external_handle.handler_ref, external_handle.handler)
    external_built = external_definition.build()
    external_run = external_runtime.run(external_built)
    external_manifest = external_runtime.manifest(external_built, external_run.run_id)

assert external_run.status.value == "SUCCEEDED"
external_ref = external_manifest.tasks[0].external_refs[0]
assert external_ref.provider == "pyingestkit"
assert external_ref.external_run_id
assert external_ref.uri == f"pyingestkit://runs/{external_ref.external_run_id}"
print("C specialized external runtime workload: ok")


# D. Optional observability adapter receives committed events without owning state.
event_registration = registration_for(PluginType.EVENT, "reference-event-sink")
assert_plugin_conforms(
    event_registration,
    entry_point_name="reference-event-sink",
    plugin_type=PluginType.EVENT,
)
event_catalog = enable(PluginType.EVENT, "reference-event-sink")
sink = event_catalog.events.create("reference-event-sink")

@task(id="observed")
def observed() -> str:
    return "ok"


@workflow(id="qualification.v0_8.d_observability", version="1")
def observed_definition():
    return (observed,)


observed_runtime = WorkflowRuntime()
observed_runtime.register_event_sink(sink)
observed_runtime.register(observed.handler_ref, observed.handler)
observed_run = observed_runtime.run(observed_definition.build())
persisted_events = observed_runtime.events(observed_run.run_id)

assert observed_run.status.value == "SUCCEEDED"
assert tuple(event.event_id for event in sink.events) == tuple(
    event.event_id for event in persisted_events
)
print("D optional observability adapter: ok")


# E. Control-plane provider operates via portable public contracts.
provider_runtime = WorkflowRuntime()
provider_runtime.register("qualification.fetch", lambda: {"rows": 2})
provider_runtime.register("qualification.publish", lambda: "published")
provider = WorkflowRuntimeProvider(provider_runtime)

provider_workflow = {
    "workflow_id": "qualification.v0_8.e_provider",
    "version": "1",
    "tasks": [
        {"task_id": "fetch", "handler_ref": "qualification.fetch"},
        {
            "task_id": "publish",
            "handler_ref": "qualification.publish",
            "depends_on": ["fetch"],
        },
    ],
}

provider_run = provider.execute_workflow(provider_workflow)
provider_manifest = provider.retrieve_manifest(provider_workflow, provider_run.run_id)
provider_lineage = provider.retrieve_lineage(provider_workflow, provider_run.run_id)

assert provider_run.status == "SUCCEEDED"
assert provider_manifest["schema_version"] == "1"
assert provider_lineage.run_id == provider_run.run_id
assert provider.inspect_capabilities().scheduling_owned_by_control_plane is True
print("E control-plane provider public contract: ok")


# F. Broken optional integration remains inert until explicit enablement and cannot break core.
core_smoke("qualification.v0_8.f_before_broken_enable")

broken_discovery = PluginDiscovery()
broken_candidates = broken_discovery.discover(plugin_types=(PluginType.EVENT,))
assert any(candidate.name == "broken-optional" for candidate in broken_candidates)

broken_catalog = PluginCatalog()
broken_report = broken_discovery.enable_selected(
    catalog=broken_catalog,
    enabled={PluginType.EVENT: {"broken-optional"}},
)
broken_result = next(
    item
    for item in broken_report.results
    if item.plugin.plugin_type is PluginType.EVENT
    and item.plugin.name == "broken-optional"
)
assert broken_result.status is PluginDiscoveryStatus.FAILED
assert len(broken_catalog.events) == 0

core_smoke("qualification.v0_8.f_after_broken_enable")
print("F broken optional integration isolation: ok")


snapshot = ecosystem_contract_snapshot()
assert snapshot["compatibility"] == {
    "series": "0.8-1.x",
    "minimum": "0.8.0b1",
    "maximum_exclusive": "2.0",
}
assert snapshot["contracts"] == {
    "control_plane": "1",
    "external_workload": "1",
    "observability": "1",
    "plugin_api": "1",
    "references": "1",
}
print("PyWorkflowKit 0.8 transverse qualification: ok")
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


def _build_wheel(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    _run(
        sys.executable,
        "-m",
        "build",
        "--wheel",
        "--outdir",
        str(destination),
        str(source),
    )
    return _single_wheel(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--core-wheel",
        type=Path,
        help="Existing PyWorkflowKit wheel. When omitted, build one from the repository.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    qualification = root / "qualification-integrations"
    references = root / "reference-integrations"

    with tempfile.TemporaryDirectory(prefix="pyworkflowkit-v0-8-transverse-") as temp:
        workspace = Path(temp)
        core_dist = workspace / "core-dist"

        if args.core_wheel is None:
            core_wheel = _build_wheel(root, core_dist)
        else:
            core_wheel = args.core_wheel.resolve()
            if not core_wheel.is_file():
                raise FileNotFoundError(core_wheel)

        wheels = (
            _build_wheel(
                qualification / "reference-executor",
                workspace / "reference-executor-dist",
            ),
            _build_wheel(
                qualification / "broken-optional",
                workspace / "broken-optional-dist",
            ),
            _build_wheel(
                references / "reference-event-sink",
                workspace / "event-sink-dist",
            ),
            _build_wheel(
                references / "reference-pyingestkit",
                workspace / "pyingestkit-adapter-dist",
            ),
        )

        environment = workspace / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        program = workspace / "transverse_conformance.py"
        program.write_text(CONFORMANCE_PROGRAM, encoding="utf-8")

        _run(str(python), "-m", "pip", "install", "--upgrade", "pip")
        _run(str(python), "-m", "pip", "install", str(core_wheel))
        _run(str(python), "-m", "pip", "install", PYINGESTKIT_REFERENCE)
        for wheel in wheels:
            _run(str(python), "-m", "pip", "install", "--no-deps", str(wheel))

        _run(str(python), str(program), cwd=workspace)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
