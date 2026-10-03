"""Unit tests for CLI bootstrap and dynamic workflow loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyworkflowkit.cli.bootstrap import load_workflow_from_spec
from pyworkflowkit.cli.security import SecurityError
from pyworkflowkit.declarative import WorkflowBuilder
from pyworkflowkit.domain.definitions import WorkflowDefinition


def test_load_workflow_from_spec_requires_colon() -> None:
    with pytest.raises(ValueError, match="module:attribute syntax"):
        load_workflow_from_spec("invalid_spec_without_colon")


def test_load_workflow_from_spec_type_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_module = tmp_path / "not_a_workflow.py"
    test_module.write_text("SOME_INT = 42\n", encoding="utf-8")

    with pytest.raises(TypeError, match="must resolve to WorkflowBuilder"):
        load_workflow_from_spec(f"{test_module}:SOME_INT", workspace_root=tmp_path)


def test_load_workflow_from_spec_with_builder(tmp_path: Path) -> None:
    test_module = tmp_path / "valid_builder.py"
    test_module.write_text(
        "from pyworkflowkit.declarative import task, workflow\n\n"
        "@task\n"
        "def step():\n"
        "    return 'ok'\n\n"
        "@workflow(id='test_wf', version='1')\n"
        "def demo():\n"
        "    return (step,)\n\n"
        "builder = demo\n",
        encoding="utf-8",
    )

    definition, builder = load_workflow_from_spec(f"{test_module}:builder", workspace_root=tmp_path)
    assert isinstance(definition, WorkflowDefinition)
    assert isinstance(builder, WorkflowBuilder)
    assert str(definition.workflow_id) == "test_wf"


def test_load_workflow_from_spec_rejects_path_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("builder = None\n", encoding="utf-8")

    with pytest.raises(SecurityError, match="resolves outside allowed workspace"):
        load_workflow_from_spec(f"{outside}:builder", workspace_root=workspace)
