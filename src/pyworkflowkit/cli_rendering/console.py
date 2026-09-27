"""Console construction for human CLI rendering."""

from __future__ import annotations

import sys
from typing import TextIO

from rich.console import Console


def console(*, error: bool = False) -> Console:
    """Create a Console bound to the active Click/Typer capture stream."""

    stream: TextIO = sys.stderr if error else sys.stdout
    return Console(file=stream, highlight=False)


__all__ = ["console"]
