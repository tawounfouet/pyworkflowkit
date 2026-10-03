"""LOT-12 reference acceptance for canonical V2 execution evidence."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.diagnostics as diagnostics
import pyworkflowkit.lineage as lineage
import pyworkflowkit.runtime as runtime
from pyworkflowkit.migrations import MIGRATION_HEAD_REVISION, MIGRATION_HISTORY
from pyworkflowkit.persistence import (
    V2_METADATA_STORE_CONTRACT_VERSION,
    V2_METADATA_STORE_METHODS,
)


def test_lot12_qualified_v2_evidence_surfaces_are_explicit() -> None:
    assert "RuntimeEvent" in runtime.__all__
    assert "RuntimeEventType" in runtime.__all__
    assert "TaskOutputCheckpoint" in runtime.__all__

    assert tuple(lineage.__all__) == (
        "ExecutionLineage",
        "ExecutionLineageProjector",
        "LineageDependency",
        "MANIFEST_SCHEMA_VERSION",
        "ManifestAttempt",
        "ManifestTaskRun",
        "RunManifest",
        "RunManifestBuilder",
        "TaskExecutionLineage",
    )

    assert "RuntimeInspection" in diagnostics.__all__
    assert "RuntimeInspector" in diagnostics.__all__
    assert "TaskInspection" in diagnostics.__all__

    assert "RunManifest" not in pyworkflowkit.__all__
    assert "TaskOutputCheckpoint" not in pyworkflowkit.__all__


def test_lot12_v2_manifest_is_distinct_from_frozen_legacy_schema() -> None:
    from pyworkflowkit.application.manifest import (
        MANIFEST_SCHEMA_VERSION as LEGACY_MANIFEST_SCHEMA_VERSION,
    )

    assert lineage.MANIFEST_SCHEMA_VERSION == "2"
    assert LEGACY_MANIFEST_SCHEMA_VERSION == "1"


def test_lot12_metadata_contract_v2_owns_durable_output_evidence() -> None:
    assert V2_METADATA_STORE_CONTRACT_VERSION == "2"
    assert V2_METADATA_STORE_METHODS[-5:] == (
        "list_runtime_events",
        "set_task_output_checkpoint",
        "get_task_output_checkpoint",
        "set_manifest_reference",
        "get_manifest_reference",
    )


def test_lot12_migration_lineage_is_append_only() -> None:
    assert MIGRATION_HISTORY[-2:] == (
        "0004_v2_runtime_metadata",
        "0005_v2_task_output_checkpoints",
    )
    assert MIGRATION_HEAD_REVISION == "0005_v2_task_output_checkpoints"


def test_lot12_event_vocabulary_is_frozen() -> None:
    assert tuple(value.value for value in runtime.RuntimeEventType) == (
        "WORKFLOW_STARTED",
        "WORKFLOW_RESUMED",
        "WORKFLOW_SUCCEEDED",
        "WORKFLOW_FAILED",
        "WORKFLOW_CANCELLATION_REQUESTED",
        "WORKFLOW_CANCELLED",
        "WORKFLOW_TIMED_OUT",
        "WORKFLOW_UNKNOWN_OUTCOME",
        "TASK_READY",
        "TASK_STARTED",
        "TASK_RETRYING",
        "TASK_SUCCEEDED",
        "TASK_FAILED",
        "TASK_SKIPPED",
        "TASK_CANCELLED",
        "TASK_TIMED_OUT",
        "TASK_BLOCKED",
        "TASK_UNKNOWN_OUTCOME",
    )
