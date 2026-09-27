"""Tree-oriented human CLI renderers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rich.text import Text
from rich.tree import Tree

from pyworkflowkit.cli_rendering.console import console


def render_plan(payload: Mapping[str, object]) -> None:
    workflow = f"{payload['workflow_id']}@{payload['workflow_version']}"
    tree = Tree(Text(f"Execution Plan · {workflow}", style="bold"))

    groups = payload.get("groups", [])
    if not isinstance(groups, Sequence):
        raise TypeError("plan groups payload must be a sequence")

    for group in groups:
        if not isinstance(group, Mapping):
            raise TypeError("plan group must be a mapping")
        stage = tree.add(Text(f"Stage {group.get('index', '-')}"))
        tasks = group.get("tasks", [])
        if not isinstance(tasks, Sequence):
            raise TypeError("plan tasks must be a sequence")
        for task_id in tasks:
            stage.add(Text(str(task_id)))

    console().print(tree)


__all__ = ["render_plan"]
