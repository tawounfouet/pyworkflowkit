"""Run command for executing or simulating workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli.services.run_service import RunService
from pyworkflowkit.cli_rendering import render_error, render_run
from pyworkflowkit.domain.enums import WorkflowRunStatus
from pyworkflowkit.errors import PyWorkflowKitError


def run_command(
    target: Annotated[
        str,
        typer.Argument(help="Decorated workflow reference as module:attribute or path.py:attr."),
    ],
    config: Annotated[
        Path | None, typer.Option("--config", help="TOML runtime configuration.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Simulate execution without running real tasks.")
    ] = False,
) -> None:
    """Execute one workflow synchronously."""
    service = RunService()
    try:
        report = service.run(target, config_path=config, dry_run=dry_run)
    except (PyWorkflowKitError, TypeError, ValueError, ImportError, AttributeError) as exc:
        error_msg = str(exc)
        if json_output:
            typer.echo(
                json.dumps(
                    {"error": error_msg, "exit_code": int(ExitCode.EXECUTION_FAILURE)},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                err=True,
            )
        else:
            render_error(error_msg)
        raise typer.Exit(int(ExitCode.EXECUTION_FAILURE)) from None

    payload = report.to_dict()

    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        title = "Workflow Run (Simulation)" if dry_run else "Workflow Run"
        render_run(payload, title=title)

    if report.status != WorkflowRunStatus.SUCCEEDED.value:
        raise typer.Exit(int(ExitCode.EXECUTION_FAILURE))
