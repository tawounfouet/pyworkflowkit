"""Executable entrypoint for python -m pyworkflowkit.cli."""

from __future__ import annotations

import sys

from pyworkflowkit.cli.bootstrap import main

if __name__ == "__main__":
    sys.exit(main())
