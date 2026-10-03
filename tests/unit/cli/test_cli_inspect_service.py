"""Unit tests for InspectService and run inspection."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyworkflowkit._compat.v1_root import TaskHandle, task, workflow
from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.cli.services.inspect_service import InspectService
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.errors import PyWorkflowKitError


def test_inspect_service_existing_run(tmp_path: Path) -> None:
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "workspace").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "test.sqlite3"\n',
        encoding="utf-8",
    )

    settings = RuntimeSettings.load(config_file=config_path)
    runtime = WorkflowRuntime(settings)

    @task
    def step_one() -> str:
        return "success"

    @workflow(id="test_inspect_flow", version="1.0")
    def inspect_flow() -> tuple[TaskHandle, ...]:
        return (step_one,)

    builder = inspect_flow
    definition = builder.build()
    for handle in builder.task_handles():
        runtime.register(handle.handler_ref, handle.handler)

    result = runtime.run(definition)

    service = InspectService()
    report = service.inspect(str(result.run_id), config_path=config_path)

    assert report.run_id == str(result.run_id)
    assert report.workflow_id == "test_inspect_flow"
    assert report.workflow_version == "1.0"
    assert report.status == "SUCCEEDED"
    assert report.created_at is not None
    assert set(report.to_dict()) == {
        "run_id",
        "workflow_id",
        "workflow_version",
        "status",
        "created_at",
        "started_at",
        "finished_at",
    }


def test_inspect_service_non_existent_run(tmp_path: Path) -> None:
    config_path = tmp_path / "pyworkflowkit.toml"
    config_path.write_text(
        f'[runtime]\nworkspace = "{(tmp_path / "ws").as_posix()}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "test.sqlite3"\n',
        encoding="utf-8",
    )

    service = InspectService()
    with pytest.raises(PyWorkflowKitError):
        service.inspect("non_existent_run_12345", config_path=config_path)
