"""Local operational CLI for PyWorkflowKit."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import typer

from pyworkflowkit import __version__
from pyworkflowkit.application.manifest import RunManifestSerializer
from pyworkflowkit.application.planning import DAGValidator, ExecutionPlanner, build_dependency_graph
from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.declarative import WorkflowBuilder
from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.enums import WorkflowRunStatus
from pyworkflowkit.domain.runtime import RuntimeEvent, WorkflowRun
from pyworkflowkit.errors import PyWorkflowKitError

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Execute and inspect local PyWorkflowKit workflows.",
)

VALIDATION_EXIT = 2
RUN_FAILURE_EXIT = 3


@app.command("version")
def version_command() -> None:
    """Print the installed PyWorkflowKit version."""

    typer.echo(__version__)


@app.command()
def validate(
    target: str = typer.Argument(..., help="Workflow reference as module:attribute."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Validate one workflow definition and its DAG."""

    try:
        definition, _ = _load_workflow(target)
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
    _emit(payload, json_output=json_output, human=f"VALID {definition.workflow_id}@{definition.version}")


@app.command()
def plan(
    target: str = typer.Argument(..., help="Workflow reference as module:attribute."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Render the deterministic execution plan."""

    try:
        definition, _ = _load_workflow(target)
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
    human = "\n".join(
        [
            f"Workflow {execution_plan.workflow_id}@{execution_plan.workflow_version}",
            *[
                f"[{group.index}] " + ", ".join(str(task_id) for task_id in group.task_ids)
                for group in execution_plan.groups
            ],
        ]
    )
    _emit(payload, json_output=json_output, human=human)


@app.command("run")
def run_command(
    target: str = typer.Argument(..., help="Decorated workflow reference as module:attribute."),
    config: Path | None = typer.Option(None, "--config", help="TOML runtime configuration."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Execute one decorated workflow synchronously."""

    try:
        definition, builder = _load_workflow(target)
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
        human=f"{result.status.value} run={result.run_id} workflow={result.workflow_id}",
    )
    if result.status is not WorkflowRunStatus.SUCCEEDED:
        raise typer.Exit(RUN_FAILURE_EXIT)


@app.command()
def inspect(
    run_id: str = typer.Argument(..., help="Workflow run identifier."),
    config: Path | None = typer.Option(None, "--config", help="TOML runtime configuration."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
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
        human=(
            f"run={run.run_id} workflow={run.workflow_id}@{run.workflow_version} "
            f"status={run.status.value}"
        ),
    )


@app.command()
def events(
    run_id: str = typer.Argument(..., help="Workflow run identifier."),
    config: Path | None = typer.Option(None, "--config", help="TOML runtime configuration."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """List persisted runtime events."""

    try:
        runtime = WorkflowRuntime(_load_settings(config))
        values = runtime.events(run_id)
    except (PyWorkflowKitError, TypeError, ValueError) as exc:
        _fail(str(exc), code=VALIDATION_EXIT, json_output=json_output)

    payload = {"run_id": run_id, "events": [_event_payload(event) for event in values]}
    human = "\n".join(
        f"{event.event_sequence}: {event.event_type.value}" for event in values
    )
    _emit(payload, json_output=json_output, human=human or "<no events>")


@app.command()
def manifest(
    target: str = typer.Argument(..., help="Workflow reference as module:attribute."),
    run_id: str = typer.Argument(..., help="Workflow run identifier."),
    config: Path | None = typer.Option(None, "--config", help="TOML runtime configuration."),
    json_output: bool = typer.Option(False, "--json", help="Emit canonical JSON."),
) -> None:
    """Build the final manifest for a persisted terminal run."""

    try:
        definition, _ = _load_workflow(target)
        runtime = WorkflowRuntime(_load_settings(config))
        value = runtime.manifest(definition, run_id)
        serializer = RunManifestSerializer()
    except (PyWorkflowKitError, TypeError, ValueError, ImportError, AttributeError) as exc:
        _fail(str(exc), code=VALIDATION_EXIT, json_output=json_output)

    if json_output:
        typer.echo(serializer.to_json(value))
    else:
        typer.echo(
            f"run={value.run_id} workflow={value.workflow_id}@{value.workflow_version} "
            f"status={value.status} tasks={len(value.tasks)} events={len(value.events)}"
        )


def main() -> None:
    """Console-script entrypoint."""

    app()


def _load_workflow(target: str) -> tuple[WorkflowDefinition, WorkflowBuilder | None]:
    module_name, separator, attribute_path = target.partition(":")
    if not separator or not module_name or not attribute_path:
        raise ValueError("workflow reference must use module:attribute syntax")

    current: Any = import_module(module_name)
    for part in attribute_path.split("."):
        current = getattr(current, part)

    if isinstance(current, WorkflowBuilder):
        return current.build(), current
    if isinstance(current, WorkflowDefinition):
        return current, None
    raise TypeError("target must resolve to WorkflowBuilder or WorkflowDefinition")


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


def _emit(payload: dict[str, object], *, json_output: bool, human: str) -> None:
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))
    else:
        typer.echo(human)


def _fail(message: str, *, code: int, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps({"error": message, "exit_code": code}, sort_keys=True, separators=(",", ":")),
            err=True,
        )
    else:
        typer.echo(f"ERROR: {message}", err=True)
    raise typer.Exit(code)


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["app", "main"]
