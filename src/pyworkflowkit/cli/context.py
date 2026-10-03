"""Presentation and execution context for PyWorkflowKit CLI commands."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class OutputMode(StrEnum):
    """Supported report output modes."""

    HUMAN = "human"
    JSON = "json"


@dataclass(frozen=True, slots=True)
class CliContext:
    """Command context with output format, verbosity, and filesystem boundaries."""

    output_mode: OutputMode = OutputMode.HUMAN
    quiet: bool = False
    verbose: bool = False
    debug: bool = False
    color: bool = True
    workspace_root: Path | None = None

    @classmethod
    def from_options(
        cls,
        *,
        json_output: bool = False,
        quiet: bool = False,
        verbose: bool = False,
        debug: bool = False,
        no_color: bool = False,
        workspace_root: Path | None = None,
    ) -> CliContext:
        """Build a presentation context from CLI options."""
        return cls(
            output_mode=OutputMode.JSON if json_output else OutputMode.HUMAN,
            quiet=quiet,
            verbose=verbose,
            debug=debug,
            color=not no_color and "NO_COLOR" not in os.environ,
            workspace_root=workspace_root,
        )

    def __post_init__(self) -> None:
        if self.quiet and self.verbose:
            raise ValueError("--quiet and --verbose cannot be used together.")
        if self.quiet and self.debug:
            raise ValueError("--quiet and --debug cannot be used together.")
        if self.output_mode is OutputMode.JSON and self.verbose:
            raise ValueError("--json and --verbose cannot be used together.")


__all__ = ["CliContext", "OutputMode"]
