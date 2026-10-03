"""Pure execution service orchestrating workflow run and simulation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.cli.bootstrap import load_workflow_from_spec
from pyworkflowkit.cli.security import assert_path_within_workspace
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.domain.runtime import WorkflowRun


@dataclass(frozen=True)
class RunReport:
    """Report detailing workflow execution results and timings."""

    run_id: str
    workflow_id: str
    workflow_version: str
    status: str
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, object]:
        """Convert to canonical dictionary compatible with CLI JSON contract."""
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class RunService:
    """Pure service for executing or simulating workflows."""

    def __init__(self, workspace: Path | None = None) -> None:
        self._workspace = workspace

    def run(
        self,
        target: str,
        config_path: Path | None = None,
        dry_run: bool = False,
    ) -> RunReport:
        """Execute or simulate a workflow target.

        Args:
            target: Specification string in format 'module:attr' or 'file.py:attr'.
            config_path: Path to optional TOML runtime configuration file.
            dry_run: When True, simulates execution without invoking real handlers.

        Returns:
            RunReport with execution run ID and final status.
        """
        if ":" in target and (target.endswith(".py") or "/" in target.split(":", 1)[0]):
            file_part = target.split(":", 1)[0]
            assert_path_within_workspace(file_part, workspace_root=self._workspace)

        definition, builder = load_workflow_from_spec(target, workspace_root=self._workspace)
        if builder is None and not hasattr(definition, "tasks"):
            raise TypeError(
                "CLI run requires a decorated WorkflowBuilder or valid WorkflowDefinition"
            )

        settings = (
            RuntimeSettings()
            if config_path is None
            else RuntimeSettings.load(config_file=config_path)
        )
        runtime = WorkflowRuntime(settings)

        def _make_dry_handler(ref_name: str) -> Any:
            def _dry_handler() -> dict[str, Any]:
                return {"dry_run": True, "handler": ref_name}

            return _dry_handler

        if builder is not None:
            for handle in builder.task_handles():
                if dry_run:
                    runtime.register(handle.handler_ref, _make_dry_handler(handle.handler_ref))
                else:
                    runtime.register(handle.handler_ref, handle.handler)

        result: WorkflowRun = runtime.run(definition)

        return RunReport(
            run_id=str(result.run_id),
            workflow_id=str(result.workflow_id),
            workflow_version=result.workflow_version,
            status=result.status.value,
            created_at=result.created_at.isoformat() if result.created_at is not None else None,
            started_at=result.started_at.isoformat() if result.started_at is not None else None,
            finished_at=result.finished_at.isoformat() if result.finished_at is not None else None,
            dry_run=dry_run,
        )
