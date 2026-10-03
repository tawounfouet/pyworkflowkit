"""Validate command for static workflow and DAG topology inspection."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli.services.validate_service import ValidateService
from pyworkflowkit.cli_rendering import render_error, render_validation


def validate_command(
    target: Annotated[
        str,
        typer.Argument(help="Workflow reference as module:attribute or path.py:attr."),
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Validate one workflow definition and its DAG topology."""
    service = ValidateService()
    report = service.validate(target)

    if not report.valid:
        error_msg = report.errors[0] if report.errors else "Workflow validation failed"
        if json_output:
            typer.echo(
                json.dumps(
                    {"error": error_msg, "exit_code": int(ExitCode.VALIDATION_ERROR)},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                err=True,
            )
        else:
            render_error(error_msg)
        raise typer.Exit(int(ExitCode.VALIDATION_ERROR)) from None

    payload = {
        "valid": True,
        "workflow_id": report.workflow_id,
        "workflow_version": report.workflow_version,
        "task_count": report.task_count,
    }

    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        render_validation(payload)
