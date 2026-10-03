"""Installed-package conformance scenarios for M50 reference integrations."""

from __future__ import annotations

import argparse
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from pyworkflowkit._compat.v1_root import TaskResult, WorkflowRuntime, task, workflow
from pyworkflowkit.domain.ids import WorkflowId, WorkflowRunId
from pyworkflowkit.domain.runtime import WorkflowRun
from pyworkflowkit.integrations import external_workload_task
from pyworkflowkit.plugins import (
    PluginCatalog,
    PluginDiscovery,
    PluginDiscoveryStatus,
    PluginType,
    assert_plugin_instance_compatible,
)


def _plugin_type(value: str) -> PluginType:
    return PluginType(value)


def _enable(plugin_type: PluginType, name: str) -> PluginCatalog:
    discovery = PluginDiscovery()
    candidates = discovery.discover(plugin_types=(plugin_type,))
    identities = {(candidate.plugin_type, candidate.name) for candidate in candidates}
    assert (plugin_type, name) in identities, (
        f"expected installed entry point {plugin_type.value}:{name}, got {sorted(identities)}"
    )

    catalog = PluginCatalog()
    report = discovery.enable_selected(
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


def _core_smoke() -> None:
    @task(id="core")
    def core() -> TaskResult:
        return TaskResult(output="core-ok")

    @workflow(id="reference.m50.core", version="1")
    def definition():
        return (core,)

    runtime = WorkflowRuntime()
    runtime.register(core.handler_ref, core.handler)
    workflow_definition = definition.build()
    run = runtime.run(workflow_definition)
    assert run.status.value == "SUCCEEDED"
    assert runtime.manifest(workflow_definition, run.run_id).tasks[0].status == "SUCCEEDED"


def _assert_absent(plugin_type: PluginType, name: str) -> None:
    candidates = PluginDiscovery().discover(plugin_types=(plugin_type,))
    identities = {(candidate.plugin_type, candidate.name) for candidate in candidates}
    assert (plugin_type, name) not in identities, (
        f"entry point {plugin_type.value}:{name} remained discoverable after uninstall"
    )


def _workload_scenario(name: str) -> None:
    catalog = _enable(PluginType.WORKLOAD, name)
    workload = catalog.workloads.create(name)

    handle = external_workload_task(
        id="external-reference",
        provider="reference-workload",
        workload_ref="reference.job",
        workload=workload,
    )

    @workflow(id="reference.m50.workload", version="1")
    def definition():
        return (handle,)

    runtime = WorkflowRuntime()
    runtime.register(handle.handler_ref, handle.handler)
    workflow_definition = definition.build()
    run = runtime.run(workflow_definition)
    manifest = runtime.manifest(workflow_definition, run.run_id)

    assert run.status.value == "SUCCEEDED"
    assert manifest.tasks[0].external_refs[0].provider == "reference-workload"
    assert manifest.tasks[0].external_refs[0].external_run_id.startswith("reference-")


def _event_scenario(name: str) -> None:
    catalog = _enable(PluginType.EVENT, name)
    sink = catalog.events.create(name)
    assert_plugin_instance_compatible(sink, plugin_type=PluginType.EVENT)

    @task(id="observed")
    def observed() -> str:
        return "ok"

    @workflow(id="reference.m50.event", version="1")
    def definition():
        return (observed,)

    runtime = WorkflowRuntime()
    runtime.register_event_sink(sink)
    runtime.register(observed.handler_ref, observed.handler)
    run = runtime.run(definition.build())
    persisted = runtime.events(run.run_id)

    assert run.status.value == "SUCCEEDED"
    assert tuple(event.event_id for event in sink.events) == tuple(
        event.event_id for event in persisted
    )


def _metadata_scenario(name: str) -> None:
    catalog = _enable(PluginType.METADATA, name)
    store = catalog.metadata.create(name)
    assert_plugin_instance_compatible(store, plugin_type=PluginType.METADATA)

    run = WorkflowRun(
        run_id=WorkflowRunId("m50-reference-run"),
        workflow_id=WorkflowId("m50-reference-workflow"),
        workflow_version="1",
        created_at=datetime.now(UTC),
    )
    with store.unit_of_work() as uow:
        uow.add_workflow_run(run)
        uow.commit()

    loaded = store.get_workflow_run(run.run_id)
    assert loaded.workflow_id == run.workflow_id
    assert tuple(item.run_id for item in store.list_workflow_runs()) == (run.run_id,)


def _pyingestkit_scenario(name: str) -> None:
    from pyingestkit import Job, Pipeline, Runner, Step
    from pyingestkit.artifacts import LocalArtifactStore

    catalog = _enable(PluginType.WORKLOAD, name)
    adapter_factory = catalog.workloads.create(name)

    class ReferenceStep(Step):
        def execute(self, context, data):
            del context, data
            return {"rows": 3, "dataset": "customers"}

    class ReferenceJob(Job):
        id = "reference.customers"
        version = "1.0.0"

        def pipeline(self) -> Pipeline:
            return Pipeline((ReferenceStep(),))

    with tempfile.TemporaryDirectory(prefix="m50-pyingestkit-") as directory:
        runner = Runner(LocalArtifactStore(Path(directory)))
        workload = adapter_factory.wrap(runner=runner, job=ReferenceJob())

        handle = external_workload_task(
            id="ingest",
            provider="pyingestkit",
            workload_ref="reference.customers",
            workload=workload,
        )

        @workflow(id="reference.m50.pyingestkit", version="1")
        def definition():
            return (handle,)

        runtime = WorkflowRuntime()
        runtime.register(handle.handler_ref, handle.handler)
        workflow_definition = definition.build()
        run = runtime.run(workflow_definition)
        manifest = runtime.manifest(workflow_definition, run.run_id)

    assert run.status.value == "SUCCEEDED"
    external_ref = manifest.tasks[0].external_refs[0]
    assert external_ref.provider == "pyingestkit"
    assert external_ref.external_run_id
    assert external_ref.uri == f"pyingestkit://runs/{external_ref.external_run_id}"
    assert external_ref.metadata["job_id"] == "reference.customers"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "scenario",
        choices=("core", "workload", "event", "metadata", "pyingestkit", "absent"),
    )
    parser.add_argument("--plugin-type")
    parser.add_argument("--name")
    args = parser.parse_args()

    if args.scenario == "core":
        _core_smoke()
        return 0

    if args.plugin_type is None or args.name is None:
        parser.error("--plugin-type and --name are required for plugin scenarios")

    plugin_type = _plugin_type(args.plugin_type)

    if args.scenario == "absent":
        _assert_absent(plugin_type, args.name)
    elif args.scenario == "workload":
        _workload_scenario(args.name)
    elif args.scenario == "event":
        _event_scenario(args.name)
    elif args.scenario == "metadata":
        _metadata_scenario(args.name)
    elif args.scenario == "pyingestkit":
        _pyingestkit_scenario(args.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
