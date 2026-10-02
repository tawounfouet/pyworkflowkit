"""LOT-01 unit tests for portable V2 execution references."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from pyworkflowkit.runtime import (
    CorrelationId,
    ExternalRunRef,
    WorkflowExecutionReference,
    WorkflowRunId,
)


def test_workflow_execution_reference_is_minimal_and_portable() -> None:
    reference = WorkflowExecutionReference(
        workflow_run_id=WorkflowRunId.parse("W-42"),
        workflow_definition_id="customer_360",
        status="RUNNING",
        started_at=datetime(2026, 10, 2, 10, 0, tzinfo=UTC),
    )

    assert str(reference.workflow_run_id) == "W-42"
    assert reference.workflow_definition_id == "customer_360"
    assert reference.owner == "pyworkflowkit"
    assert reference.contract_version == "1"


def test_workflow_execution_reference_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        WorkflowExecutionReference(
            workflow_run_id=WorkflowRunId.parse("W-42"),
            workflow_definition_id="customer_360",
            started_at=datetime(2026, 10, 2, 10, 0),
        )


def test_external_run_ref_is_authority_neutral_portable_evidence() -> None:
    reference = ExternalRunRef(
        provider="pytransformkit",
        external_run_id="T-913",
        kind="transformation_execution",
        status_hint="UNKNOWN_OUTCOME",
        status_locator="transformations/T-913",
        correlation_id=CorrelationId.parse("C-42"),
        causation_id="TA-3",
        metadata=(("engine", "duckdb"),),
    )

    assert reference.provider == "pytransformkit"
    assert reference.external_run_id == "T-913"
    assert reference.contract_version == "1"
    assert not hasattr(reference, "cancel")
    assert not hasattr(reference, "reconcile")


def test_external_run_ref_is_immutable() -> None:
    reference = ExternalRunRef(
        provider="pyingestkit",
        external_run_id="I-288",
        kind="ingestion_run",
    )

    with pytest.raises(FrozenInstanceError):
        reference.external_run_id = "I-289"  # type: ignore[misc]


def test_external_run_ref_requires_explicit_execution_kind() -> None:
    with pytest.raises(ValueError):
        ExternalRunRef(
            provider="snowflake",
            external_run_id="01b...",
            kind=" ",
        )
