"""Typer application for the PyWorkflowKit operational CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pyworkflowkit import __version__
from pyworkflowkit.cli.commands.doctor import doctor_command
from pyworkflowkit.cli.commands.inspect import inspect_command
from pyworkflowkit.cli.commands.legacy import (
    events_command,
    manifest_command,
    plugins_command,
    run_command,
)
from pyworkflowkit.cli.commands.plan import plan_command
from pyworkflowkit.cli.commands.validate import validate_command
from pyworkflowkit.cli.commands.version import version_command
from pyworkflowkit.cli.context import CliContext

app = typer.Typer(
    name="pwk",
    help="Execute and inspect local PyWorkflowKit workflows.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            is_eager=True,
            help="Show the installed PyWorkflowKit version and exit.",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential console outputs."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose execution logs."),
    ] = False,
    cwd: Annotated[
        Path | None,
        typer.Option("--cwd", help="Override working directory / workspace boundary root."),
    ] = None,
) -> None:
    """Execute and inspect local PyWorkflowKit workflows."""
    if version:
        typer.echo(__version__)
        raise typer.Exit(0)

    ctx.obj = CliContext.from_options(
        quiet=quiet,
        verbose=verbose,
        workspace_root=cwd,
    )


# Register all commands
app.command("version")(version_command)
app.command("doctor")(doctor_command)
app.command("validate")(validate_command)
app.command("plan")(plan_command)
app.command("run")(run_command)
app.command("inspect")(inspect_command)
app.command("events")(events_command)
app.command("manifest")(manifest_command)
app.command("plugins")(plugins_command)

__all__ = ["app"]
