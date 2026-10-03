"""Unit tests for RunService execution and simulation."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from pyworkflowkit._compat.v1_root import TaskHandle, task, workflow
from pyworkflowkit.cli.security import SecurityError
from pyworkflowkit.cli.services.run_service import RunService
from pyworkflowkit.errors import PyWorkflowKitError


def _setup_module(monkeypatch: pytest.MonkeyPatch, name: str) -> str:
    mod = ModuleType(name)

    called: list[str] = []

    @task
    def t1() -> str:
        called.append("t1")
        return "step 1"

    @workflow(id="run_svc.flow", version="1.0")
    def my_flow() -> tuple[TaskHandle, ...]:
        return (t1,)

    mod.my_flow = my_flow  # type: ignore[attr-defined]
    mod.called = called  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, mod)
    return f"{name}:my_flow"


def test_run_service_normal_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _setup_module(monkeypatch, "mod_run_svc_normal")
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "run.sqlite3"\n',
        encoding="utf-8",
    )

    service = RunService()
    report = service.run(target, config_path=config_path, dry_run=False)

    assert report.workflow_id == "run_svc.flow"
    assert report.workflow_version == "1.0"
    assert report.status == "SUCCEEDED"
    assert report.dry_run is False
    assert report.run_id != ""

    mod = sys.modules["mod_run_svc_normal"]
    assert "t1" in mod.called


def test_run_service_dry_run_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _setup_module(monkeypatch, "mod_run_svc_dry")
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "run.sqlite3"\n',
        encoding="utf-8",
    )

    service = RunService()
    report = service.run(target, config_path=config_path, dry_run=True)

    assert report.workflow_id == "run_svc.flow"
    assert report.status == "SUCCEEDED"
    assert report.dry_run is True

    mod = sys.modules["mod_run_svc_dry"]
    # The real task was NOT called because of dry-run simulation
    assert "t1" not in mod.called


def test_run_service_rejects_path_traversal() -> None:
    service = RunService()
    with pytest.raises(SecurityError):
        service.run("../../../etc/passwd:flow")


def test_run_service_invalid_target() -> None:
    service = RunService()
    with pytest.raises((PyWorkflowKitError, ModuleNotFoundError, ValueError)):
        service.run("non_existent_pkg_xyz:flow")
