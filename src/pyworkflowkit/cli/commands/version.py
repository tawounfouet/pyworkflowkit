"""Version command for PyWorkflowKit CLI."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from pyworkflowkit import __version__


def version_command(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Print the installed PyWorkflowKit version."""
    if json_output:
        typer.echo(json.dumps({"version": __version__}, sort_keys=True))
    else:
        typer.echo(__version__)


__all__ = ["version_command"]
