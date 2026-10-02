"""V2 semantic planning namespace.

The current ExecutionPlan is exposed as a migration baseline. WorkflowPlanner and
the final V2 compiled-plan contract are introduced by LOT-03.
"""

from pyworkflowkit.application.planning import ExecutionPlan

__all__ = ["ExecutionPlan"]
