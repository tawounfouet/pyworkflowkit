"""Pure planning service for workflow compilation and graph visualization."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pyworkflowkit.application.planning import (
    DAGValidator,
    ExecutionPlanner,
    build_dependency_graph,
)
from pyworkflowkit.cli.bootstrap import load_workflow_from_spec
from pyworkflowkit.cli.security import assert_path_within_workspace


@dataclass(frozen=True)
class PlanGroup:
    """A concurrency group within an execution plan."""

    index: int
    tasks: tuple[str, ...]


@dataclass(frozen=True)
class PlanReport:
    """Report detailing workflow compilation and execution plan."""

    target: str
    workflow_id: str
    workflow_version: str
    groups: tuple[PlanGroup, ...]
    dependencies: dict[str, tuple[str, ...]] = field(default_factory=dict)
    task_count: int = 0

    def to_dict(self) -> dict[str, object]:
        """Convert to canonical dictionary compatible with CLI JSON contract."""
        return {
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "groups": [{"index": group.index, "tasks": list(group.tasks)} for group in self.groups],
        }


class PlanService:
    """Pure service for workflow execution planning and graph rendering."""

    def __init__(self, workspace: Path | None = None) -> None:
        self._workspace = workspace

    def plan(self, target: str) -> PlanReport:
        """Compile one workflow target into an execution plan.

        Args:
            target: Specification string in format 'module:attr' or 'file.py:attr'.

        Returns:
            PlanReport with concurrency groups and dependency mappings.
        """
        if ":" in target and (target.endswith(".py") or "/" in target.split(":", 1)[0]):
            file_part = target.split(":", 1)[0]
            assert_path_within_workspace(file_part, workspace_root=self._workspace)

        definition, _ = load_workflow_from_spec(target, workspace_root=self._workspace)
        graph = build_dependency_graph(definition)
        DAGValidator().validate(definition, graph)
        execution_plan = ExecutionPlanner().build_plan(definition, graph)

        groups = tuple(
            PlanGroup(
                index=group.index,
                tasks=tuple(str(t_id) for t_id in group.task_ids),
            )
            for group in execution_plan.groups
        )

        dependencies: dict[str, tuple[str, ...]] = {}
        for task in definition.tasks:
            dependencies[str(task.task_id)] = tuple(str(d) for d in task.depends_on)

        return PlanReport(
            target=target,
            workflow_id=str(execution_plan.workflow_id),
            workflow_version=execution_plan.workflow_version,
            groups=groups,
            dependencies=dependencies,
            task_count=len(definition.tasks),
        )

    def generate_mermaid(self, report: PlanReport) -> str:
        """Generate Mermaid graph syntax for workflow dependencies.

        Returns:
            Mermaid formatted string.
        """
        lines: list[str] = ["graph TD"]
        has_edges = False

        for task_id, deps in report.dependencies.items():
            if deps:
                for dep in deps:
                    lines.append(f'    {dep}["{dep}"] --> {task_id}["{task_id}"]')
                    has_edges = True
            else:
                # Standalone task if no outgoing or incoming
                is_referenced = any(
                    task_id in other_deps for other_deps in report.dependencies.values()
                )
                if not is_referenced:
                    lines.append(f'    {task_id}["{task_id}"]')

        if not has_edges and not lines[1:]:
            for group in report.groups:
                for task in group.tasks:
                    lines.append(f'    {task}["{task}"]')

        return "\n".join(lines)

    def generate_ascii(self, report: PlanReport) -> str:
        """Generate ASCII visualization of execution stages."""
        lines: list[str] = [
            f"Workflow Plan: {report.workflow_id} (v{report.workflow_version})",
            f"Total Tasks: {report.task_count}, Concurrency Stages: {len(report.groups)}",
            "",
        ]

        for group in report.groups:
            tasks_str = ", ".join(group.tasks)
            lines.append(f"  Stage {group.index}: [{tasks_str}]")
            if group.index < len(report.groups) - 1:
                lines.append("       │")
                lines.append("       ▼")

        return "\n".join(lines)
