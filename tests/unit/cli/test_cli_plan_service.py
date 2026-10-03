"""Unit tests for PlanService, Mermaid, and ASCII generation."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from pyworkflowkit._compat.v1_root import TaskHandle, task, workflow
from pyworkflowkit.cli.security import SecurityError
from pyworkflowkit.cli.services.plan_service import PlanService


def _install_test_module(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    mod = ModuleType(name)

    @task
    def fetch() -> str:
        return "raw"

    @task(depends_on=(fetch,))
    def transform() -> str:
        return "clean"

    @task(depends_on=(transform,))
    def publish() -> str:
        return "done"

    @workflow(id="etl.flow", version="2.0")
    def etl_workflow() -> tuple[TaskHandle, ...]:
        return (fetch, transform, publish)

    mod.etl_workflow = etl_workflow  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, mod)


def test_plan_service_compiles_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    mod_name = "test_plan_service_mod"
    _install_test_module(monkeypatch, mod_name)

    service = PlanService()
    report = service.plan(f"{mod_name}:etl_workflow")

    assert report.workflow_id == "etl.flow"
    assert report.workflow_version == "2.0"
    assert len(report.groups) == 3
    assert report.task_count == 3
    assert set(report.to_dict()) == {"workflow_id", "workflow_version", "groups"}


def test_plan_service_mermaid_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    mod_name = "test_plan_mermaid_mod"
    _install_test_module(monkeypatch, mod_name)

    service = PlanService()
    report = service.plan(f"{mod_name}:etl_workflow")
    mermaid = service.generate_mermaid(report)

    assert "graph TD" in mermaid
    assert "-->" in mermaid
    assert "fetch" in mermaid
    assert "transform" in mermaid
    assert "publish" in mermaid


def test_plan_service_ascii_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    mod_name = "test_plan_ascii_mod"
    _install_test_module(monkeypatch, mod_name)

    service = PlanService()
    report = service.plan(f"{mod_name}:etl_workflow")
    ascii_out = service.generate_ascii(report)

    assert "Workflow Plan: etl.flow (v2.0)" in ascii_out
    assert "Stage 0:" in ascii_out
    assert "Stage 1:" in ascii_out
    assert "Stage 2:" in ascii_out


def test_plan_service_rejects_path_traversal() -> None:
    service = PlanService()
    with pytest.raises(SecurityError):
        service.plan("../../../etc/shadow:flow")
