"""Unit tests for ValidateService and topology inspection."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from pyworkflowkit._compat.v1_root import TaskHandle, task, workflow
from pyworkflowkit.cli.security import SecurityError
from pyworkflowkit.cli.services.validate_service import ValidateService
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.ids import TaskId, WorkflowId


def _install_test_module(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    mod = ModuleType(name)

    @task
    def task_a() -> str:
        return "a"

    @task(depends_on=(task_a,))
    def task_b() -> str:
        return "b"

    @workflow(id="valid.flow", version="1.0")
    def valid_workflow() -> tuple[TaskHandle, ...]:
        return (task_a, task_b)

    # Cyclic workflow
    cyclic_workflow = WorkflowDefinition(
        workflow_id=WorkflowId("cyclic.flow"),
        version="1.0",
        tasks=(
            TaskDefinition(task_id=TaskId("A"), depends_on=(TaskId("B"),)),
            TaskDefinition(task_id=TaskId("B"), depends_on=(TaskId("A"),)),
        ),
    )

    mod.valid_workflow = valid_workflow  # type: ignore[attr-defined]
    mod.cyclic_workflow = cyclic_workflow  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, mod)


def test_validate_service_valid_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    mod_name = "test_validate_service_mod"
    _install_test_module(monkeypatch, mod_name)

    service = ValidateService()
    report = service.validate(f"{mod_name}:valid_workflow")

    assert report.valid is True
    assert report.workflow_id == "valid.flow"
    assert report.workflow_version == "1.0"
    assert report.task_count == 2
    assert report.cycle_detected is False
    assert len(report.errors) == 0


def test_validate_service_cyclic_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    mod_name = "test_validate_cyclic_mod"
    _install_test_module(monkeypatch, mod_name)

    service = ValidateService()
    report = service.validate(f"{mod_name}:cyclic_workflow")

    assert report.valid is False
    assert report.cycle_detected is True
    assert len(report.errors) > 0


def test_validate_service_non_existent_target() -> None:
    service = ValidateService()
    report = service.validate("non_existent_module_foo:workflow")

    assert report.valid is False
    assert len(report.errors) > 0


def test_validate_service_rejects_path_traversal() -> None:
    service = ValidateService()
    with pytest.raises(SecurityError):
        service.validate("../etc/passwd:workflow")
