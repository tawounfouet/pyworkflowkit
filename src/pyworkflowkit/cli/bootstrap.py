"""Dependency-light bootstrap and workflow dynamic loader for PyWorkflowKit CLI."""

from __future__ import annotations

import errno
import importlib
import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli.security import assert_path_within_workspace

CLI_DEPENDENCIES = ("typer", "rich")
MISSING_DEPENDENCY_EXIT_CODE = int(ExitCode.USER_ERROR)


def _missing_cli_dependencies() -> tuple[str, ...]:
    return tuple(dep for dep in CLI_DEPENDENCIES if importlib.util.find_spec(dep) is None)


def load_workflow_from_spec(
    spec: str,
    workspace_root: Path | None = None,
) -> tuple[Any, Any | None]:
    """Load a workflow definition and optional builder from a target specification.

    Accepts target as either:
    - 'module.path:workflow_attribute'
    - 'path/to/file.py:workflow_attribute'
    """
    target = spec.strip()
    module_or_path, separator, attribute_path = target.partition(":")
    if not separator or not module_or_path or not attribute_path:
        raise ValueError("workflow reference must use module:attribute syntax")

    # If target points to a python file on disk, validate workspace boundary
    if module_or_path.endswith(".py") or "/" in module_or_path or "\\" in module_or_path:
        file_path = Path(module_or_path)
        safe_path = assert_path_within_workspace(file_path, workspace_root)
        module_dir = str(safe_path.parent)
        if module_dir not in sys.path:
            sys.path.insert(0, module_dir)
        module_name = safe_path.stem
    else:
        module_name = module_or_path
        working_directory = str((workspace_root or Path.cwd()).resolve())
        if working_directory not in sys.path:
            sys.path.insert(0, working_directory)

    current: Any = importlib.import_module(module_name)
    for part in attribute_path.split("."):
        current = getattr(current, part)

    # Check for WorkflowBuilder (declarative V1)
    if hasattr(current, "build") and callable(current.build):
        return current.build(), current
    # Check for workflow definition or callable workflow declaration
    if hasattr(current, "workflow_id") or hasattr(current, "tasks"):
        return current, None
    if callable(current):
        built = current()
        if hasattr(built, "workflow_id") or hasattr(built, "tasks"):
            return built, None

    raise TypeError(
        f"target '{spec}' must resolve to WorkflowBuilder, "
        "WorkflowDefinition or Workflow declaration"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run pwk while keeping heavy dependencies guarded."""
    missing = _missing_cli_dependencies()
    if missing:
        print(
            f"PyWorkflowKit CLI dependencies missing: {', '.join(missing)}.\n"
            "Install CLI dependencies via: pip install pyworkflowkit[cli] "
            "or pip install typer rich",
            file=sys.stderr,
        )
        return MISSING_DEPENDENCY_EXIT_CODE

    from pyworkflowkit.cli.app import app

    args = list(argv) if argv is not None else None
    try:
        app(args=args, prog_name="pwk", standalone_mode=True)
    except BrokenPipeError:
        return int(ExitCode.BROKEN_PIPE)
    except OSError as exc:
        if exc.errno == errno.EPIPE:
            return int(ExitCode.BROKEN_PIPE)
        raise
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 1
    return 0


__all__ = ["load_workflow_from_spec", "main"]
