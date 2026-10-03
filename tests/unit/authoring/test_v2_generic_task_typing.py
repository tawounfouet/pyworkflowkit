"""Unit tests for LOT-32 generic TaskDefinition static typing and runtime inspection."""

from __future__ import annotations

from pyworkflowkit.authoring import TaskDefinition


def _sample_handler(x: int) -> str:
    return str(x)


def test_generic_task_definition_types() -> None:
    # Generic annotation with input/output types
    task_typed: TaskDefinition[int, str] = TaskDefinition(
        key="int_to_str",
        workload=_sample_handler,
    )

    assert task_typed.key == "int_to_str"
    assert task_typed.workload is _sample_handler


def test_unparameterized_task_definition_defaults_to_any() -> None:
    # Default unparameterized generic instantiation
    task_default = TaskDefinition(
        key="default_task",
        workload=_sample_handler,
    )

    assert task_default.key == "default_task"


def test_complex_generic_types() -> None:
    task_complex: TaskDefinition[dict[str, list[int]], tuple[str, bool]] = TaskDefinition(
        key="complex_task",
        workload=lambda data: ("ok", True),
    )

    assert task_complex.key == "complex_task"
