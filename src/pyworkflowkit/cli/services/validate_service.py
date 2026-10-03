"""Pure validation service for workflow DAG topologies."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pyworkflowkit.application.planning import DAGValidator, build_dependency_graph
from pyworkflowkit.cli.bootstrap import load_workflow_from_spec
from pyworkflowkit.cli.security import assert_path_within_workspace
from pyworkflowkit.errors import PyWorkflowKitError


@dataclass(frozen=True)
class ValidationReport:
    """Report detailing workflow topology validation results."""

    target: str
    valid: bool
    workflow_id: str = ""
    workflow_version: str = ""
    task_count: int = 0
    cycle_detected: bool = False
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    tasks: tuple[str, ...] = field(default_factory=tuple)


class ValidateService:
    """Pure service for static topology and DAG validation without runtime dependencies."""

    def __init__(self, workspace: Path | None = None) -> None:
        self._workspace = workspace

    def validate(self, target: str) -> ValidationReport:
        """Validate one workflow specification and verify acyclicity and dependencies.

        Args:
            target: Specification string in format 'module:attr' or 'file.py:attr'.

        Returns:
            ValidationReport describing whether the workflow is valid.
        """
        # Validate path safety if a file path is passed
        if ":" in target and (target.endswith(".py") or "/" in target.split(":", 1)[0]):
            file_part = target.split(":", 1)[0]
            assert_path_within_workspace(file_part, workspace_root=self._workspace)

        try:
            definition, _ = load_workflow_from_spec(target, workspace_root=self._workspace)
            graph = build_dependency_graph(definition)
            DAGValidator().validate(definition, graph)
        except (PyWorkflowKitError, TypeError, ValueError, ImportError, AttributeError) as exc:
            msg = str(exc)
            cycle = "cycle" in msg.lower()
            return ValidationReport(
                target=target,
                valid=False,
                cycle_detected=cycle,
                errors=(msg,),
            )

        task_names = tuple(str(task.task_id) for task in definition.tasks)
        return ValidationReport(
            target=target,
            valid=True,
            workflow_id=str(definition.workflow_id),
            workflow_version=definition.version,
            task_count=len(definition.tasks),
            cycle_detected=False,
            tasks=task_names,
        )
