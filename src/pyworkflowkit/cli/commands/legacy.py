"""Legacy commands preserved for backwards compatibility with V1.x/2.0 contract."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Annotated

import typer

from pyworkflowkit.application.manifest import RunManifestSerializer
from pyworkflowkit.application.planning import (
    DAGValidator,
    ExecutionPlanner,
    build_dependency_graph,
)
from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.cli.bootstrap import load_workflow_from_spec
from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli_rendering import (
    render_error,
    render_events,
    render_manifest,
    render_plan,
    render_plugins,
    render_run,
    render_validation,
)
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.domain.enums import WorkflowRunStatus
from pyworkflowkit.domain.runtime import RuntimeEvent, WorkflowRun
from pyworkflowkit.errors import PyWorkflowKitError
from pyworkflowkit.plugins import PluginDiscovery

VALIDATION_EXIT = int(ExitCode.VALIDATION_ERROR)
RUN_FAILURE_EXIT = int(ExitCode.EXECUTION_FAILURE)


def _load_settings(config: Path | None) -> RuntimeSettings:
    if config is None:
        return RuntimeSettings()
    return RuntimeSettings.load(config_file=config)


def _run_payload(run: WorkflowRun) -> dict[str, object]:
    return {
        "run_id": str(run.run_id),
        "workflow_id": str(run.workflow_id),
        "workflow_version": run.workflow_version,
        "status": run.status.value,
        "created_at": run.created_at.isoformat() if run.created_at is not None else None,
        "started_at": run.started_at.isoformat() if run.started_at is not None else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at is not None else None,
    }


def _event_payload(event: RuntimeEvent) -> dict[str, object]:
    return {
        "event_id": str(event.event_id),
        "event_sequence": event.event_sequence,
        "event_type": event.event_type.value,
        "occurred_at": event.occurred_at.isoformat(),
        "task_run_id": str(event.task_run_id) if event.task_run_id is not None else None,
        "task_id": str(event.task_id) if event.task_id is not None else None,
        "attempt_number": event.attempt_number,
        "payload": dict(event.payload),
    }


def _emit(
    payload: Mapping[str, object],
    *,
    json_output: bool,
    renderer: Callable[[Mapping[str, object]], None],
) -> None:
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))
    else:
        renderer(payload)


def _fail(message: str, *, code: int, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                {"error": message, "exit_code": code},
                sort_keys=True,
                separators=(",", ":"),
            ),
            err=True,
        )
    else:
        render_error(message)
    raise typer.Exit(code)


def validate_command(
    target: Annotated[str, typer.Argument(help="Workflow reference as module:attribute.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Validate one workflow definition and its DAG."""
    try:
        definition, _ = load_workflow_from_spec(target)
        graph = build_dependency_graph(definition)
        DAGValidator().validate(definition, graph)
    except (PyWorkflowKitError, TypeError, ValueError, ImportError, AttributeError) as exc:
        _fail(str(exc), code=VALIDATION_EXIT, json_output=json_output)

    payload = {
        "valid": True,
        "workflow_id": str(definition.workflow_id),
        "workflow_version": definition.version,
        "task_count": len(definition.tasks),
    }
    _emit(payload, json_output=json_output, renderer=render_validation)


def plan_command(
    target: str = typer.Argument(..., help="Workflow reference as module:attribute."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Render the deterministic execution plan."""
    try:
        definition, _ = load_workflow_from_spec(target)
        graph = build_dependency_graph(definition)
        DAGValidator().validate(definition, graph)
        execution_plan = ExecutionPlanner().build_plan(definition, graph)
    except (PyWorkflowKitError, TypeError, ValueError, ImportError, AttributeError) as exc:
        _fail(str(exc), code=VALIDATION_EXIT, json_output=json_output)

    groups = [
        {"index": group.index, "tasks": [str(task_id) for task_id in group.task_ids]}
        for group in execution_plan.groups
    ]
    payload = {
        "workflow_id": str(execution_plan.workflow_id),
        "workflow_version": execution_plan.workflow_version,
        "groups": groups,
    }
    _emit(payload, json_output=json_output, renderer=render_plan)


def run_command(
    target: Annotated[
        str, typer.Argument(help="Decorated workflow reference as module:attribute.")
    ],
    config: Annotated[
        Path | None, typer.Option("--config", help="TOML runtime configuration.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Execute one decorated workflow synchronously."""
    try:
        definition, builder = load_workflow_from_spec(target)
        if builder is None:
            raise TypeError("CLI run requires a decorated WorkflowBuilder target")
        runtime = WorkflowRuntime(_load_settings(config))
        for handle in builder.task_handles():
            runtime.register(handle.handler_ref, handle.handler)
        result = runtime.run(definition)
    except (PyWorkflowKitError, TypeError, ValueError, ImportError, AttributeError) as exc:
        _fail(str(exc), code=RUN_FAILURE_EXIT, json_output=json_output)

    payload = _run_payload(result)
    _emit(
        payload,
        json_output=json_output,
        renderer=lambda value: render_run(value, title="Workflow Run"),
    )
    if result.status is not WorkflowRunStatus.SUCCEEDED:
        raise typer.Exit(RUN_FAILURE_EXIT)


def inspect_command(
    run_id: Annotated[str, typer.Argument(help="Workflow run identifier.")],
    config: Annotated[
        Path | None, typer.Option("--config", help="TOML runtime configuration.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Inspect one persisted workflow run."""
    try:
        runtime = WorkflowRuntime(_load_settings(config))
        run = runtime.get_run(run_id)
    except (PyWorkflowKitError, TypeError, ValueError) as exc:
        _fail(str(exc), code=VALIDATION_EXIT, json_output=json_output)

    payload = _run_payload(run)
    _emit(
        payload,
        json_output=json_output,
        renderer=lambda value: render_run(value, title="Persisted Workflow Run"),
    )


def events_command(
    run_id: Annotated[str, typer.Argument(help="Workflow run identifier.")],
    config: Annotated[
        Path | None, typer.Option("--config", help="TOML runtime configuration.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """List persisted runtime events."""
    try:
        runtime = WorkflowRuntime(_load_settings(config))
        values = runtime.events(run_id)
    except (PyWorkflowKitError, TypeError, ValueError) as exc:
        _fail(str(exc), code=VALIDATION_EXIT, json_output=json_output)

    payload = {"run_id": run_id, "events": [_event_payload(event) for event in values]}
    _emit(payload, json_output=json_output, renderer=render_events)


def manifest_command(
    target: Annotated[str, typer.Argument(help="Workflow reference as module:attribute.")],
    run_id: Annotated[str, typer.Argument(help="Workflow run identifier.")],
    config: Annotated[
        Path | None, typer.Option("--config", help="TOML runtime configuration.")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit canonical JSON.")] = False,
) -> None:
    """Build the final manifest for a persisted terminal run."""
    try:
        definition, _ = load_workflow_from_spec(target)
        runtime = WorkflowRuntime(_load_settings(config))
        value = runtime.manifest(definition, run_id)
        serializer = RunManifestSerializer()
    except (PyWorkflowKitError, TypeError, ValueError, ImportError, AttributeError) as exc:
        _fail(str(exc), code=VALIDATION_EXIT, json_output=json_output)

    if json_output:
        typer.echo(serializer.to_json(value))
    else:
        render_manifest(
            {
                "run_id": str(value.run_id),
                "workflow_id": str(value.workflow_id),
                "workflow_version": value.workflow_version,
                "status": value.status,
                "task_count": len(value.tasks),
                "event_count": len(value.events),
            }
        )


def plugins_command(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """List installed PyWorkflowKit plugin entry points without loading them."""
    discovered = PluginDiscovery().discover()
    plugins_payload = [
        {
            "name": plugin.name,
            "type": plugin.plugin_type.value,
            "group": plugin.group,
            "value": plugin.value,
            "distribution": plugin.distribution,
            "status": "discovered",
        }
        for plugin in discovered
    ]
    payload: dict[str, object] = {
        "count": len(plugins_payload),
        "plugins": plugins_payload,
    }
    _emit(payload, json_output=json_output, renderer=render_plugins)


__all__ = [
    "RUN_FAILURE_EXIT",
    "VALIDATION_EXIT",
    "events_command",
    "inspect_command",
    "manifest_command",
    "plan_command",
    "plugins_command",
    "run_command",
    "validate_command",
]
