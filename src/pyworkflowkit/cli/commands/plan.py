"""Plan command for workflow compilation and execution graph rendering."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli.services.plan_service import PlanService
from pyworkflowkit.cli_rendering import render_error, render_plan
from pyworkflowkit.errors import PyWorkflowKitError


def plan_command(
    target: Annotated[
        str,
        typer.Argument(help="Workflow reference as module:attribute or path.py:attr."),
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
    format_opt: Annotated[
        str | None,
        typer.Option("--format", "-f", help="Output format: 'human', 'mermaid', 'ascii', 'json'."),
    ] = None,
    mermaid: Annotated[
        bool, typer.Option("--mermaid", help="Render plan as Mermaid graph TD syntax.")
    ] = False,
    ascii_graph: Annotated[
        bool, typer.Option("--ascii", help="Render plan as ASCII execution stages.")
    ] = False,
) -> None:
    """Render the deterministic execution plan."""
    service = PlanService()
    try:
        report = service.plan(target)
    except (PyWorkflowKitError, TypeError, ValueError, ImportError, AttributeError) as exc:
        error_msg = str(exc)
        if json_output or format_opt == "json":
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

    # Priority of outputs
    if mermaid or format_opt == "mermaid":
        typer.echo(service.generate_mermaid(report))
        return

    if ascii_graph or format_opt == "ascii":
        typer.echo(service.generate_ascii(report))
        return

    payload = report.to_dict()

    if json_output or format_opt == "json":
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        render_plan(payload)
