"""Pure inspection service for querying persisted workflow runs and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.domain.runtime import WorkflowRun


@dataclass(frozen=True)
class InspectReport:
    """Report detailing persisted workflow run metadata."""

    run_id: str
    workflow_id: str
    workflow_version: str
    status: str
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    task_runs: tuple[dict[str, object], ...] = field(default_factory=tuple)
    events_count: int = 0

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


class InspectService:
    """Pure service for querying persisted workflow execution states."""

    def __init__(self, workspace: Path | None = None) -> None:
        self._workspace = workspace

    def inspect(self, run_id: str, config_path: Path | None = None) -> InspectReport:
        """Inspect a persisted workflow run by its ID.

        Args:
            run_id: Identifier of the workflow run.
            config_path: Path to optional TOML runtime configuration file.

        Returns:
            InspectReport with run lifecycle details.
        """
        settings = (
            RuntimeSettings()
            if config_path is None
            else RuntimeSettings.load(config_file=config_path)
        )
        runtime = WorkflowRuntime(settings)
        run: WorkflowRun = runtime.get_run(run_id)

        events_count = 0
        try:
            events = runtime.events(run_id)
            events_count = len(events)
        except Exception:
            events_count = 0

        return InspectReport(
            run_id=str(run.run_id),
            workflow_id=str(run.workflow_id),
            workflow_version=run.workflow_version,
            status=run.status.value,
            created_at=run.created_at.isoformat() if run.created_at is not None else None,
            started_at=run.started_at.isoformat() if run.started_at is not None else None,
            finished_at=run.finished_at.isoformat() if run.finished_at is not None else None,
            events_count=events_count,
        )
