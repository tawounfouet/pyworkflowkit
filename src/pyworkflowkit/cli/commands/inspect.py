"""Inspect command for auditing persisted workflow runs and metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli.services.inspect_service import InspectService
from pyworkflowkit.cli_rendering import render_error, render_run
from pyworkflowkit.errors import PyWorkflowKitError


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
    service = InspectService()
    try:
        report = service.inspect(run_id, config_path=config)
    except (PyWorkflowKitError, TypeError, ValueError, KeyError) as exc:
        error_msg = str(exc)
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

    payload = report.to_dict()

    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        render_run(payload, title="Persisted Workflow Run")
