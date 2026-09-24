"""Tests for immutable domain value objects."""

from dataclasses import FrozenInstanceError
from operator import setitem

import pytest

from pyworkflowkit.domain.enums import BackoffStrategy
from pyworkflowkit.domain.ids import ArtifactId, ExternalRunRefId
from pyworkflowkit.domain.values import (
    ArtifactReference,
    ExternalRunRef,
    RetryPolicy,
    TaskResult,
    WorkflowParameter,
)


def test_retry_policy_defaults_to_single_attempt_without_backoff() -> None:
    policy = RetryPolicy()

    assert policy.max_attempts == 1
    assert policy.backoff_strategy is BackoffStrategy.NONE
    assert policy.delay_seconds == 0.0
    assert policy.max_delay_seconds is None
    assert policy.retryable_error_categories == frozenset()


@pytest.mark.parametrize("value", [0, -1])
def test_retry_policy_rejects_invalid_attempt_count(value: int) -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=value)


def test_retry_policy_rejects_boolean_attempt_count() -> None:
    with pytest.raises(TypeError, match="max_attempts"):
        RetryPolicy(max_attempts=True)


@pytest.mark.parametrize("value", [-0.1, float("inf"), float("nan")])
def test_retry_policy_rejects_invalid_delay(value: float) -> None:
    with pytest.raises(ValueError, match="delay_seconds"):
        RetryPolicy(delay_seconds=value)


def test_retry_policy_rejects_invalid_max_delay_type() -> None:
    with pytest.raises(TypeError, match="max_delay_seconds"):
        RetryPolicy(max_delay_seconds=True)


def test_retry_policy_accepts_finite_non_negative_max_delay() -> None:
    policy = RetryPolicy(
        max_attempts=3,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        delay_seconds=1.0,
        max_delay_seconds=10.0,
    )

    assert policy.max_delay_seconds == 10.0


def test_retry_policy_copies_retryable_categories() -> None:
    categories = {"transient", "network"}
    policy = RetryPolicy(retryable_error_categories=frozenset(categories))

    categories.add("database")

    assert policy.retryable_error_categories == frozenset({"transient", "network"})


def test_retry_policy_rejects_blank_error_category() -> None:
    with pytest.raises(ValueError, match="retryable_error_category"):
        RetryPolicy(retryable_error_categories=frozenset({" "}))


def test_retry_policy_is_frozen() -> None:
    policy = RetryPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.max_attempts = 2  # type: ignore[misc]


def test_artifact_reference_accepts_lightweight_metadata_and_freezes_it() -> None:
    source = {"row_count": 42}
    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact-1"),
        name="report.csv",
        uri="file:///tmp/report.csv",
        media_type="text/csv",
        checksum="sha256:123",
        size_bytes=12,
        metadata=source,
    )

    source["row_count"] = 99

    assert artifact.metadata["row_count"] == 42
    with pytest.raises(TypeError):
        setitem(artifact.metadata, "row_count", 7)


def test_artifact_reference_rejects_blank_artifact_id() -> None:
    with pytest.raises(ValueError, match="artifact_id"):
        ArtifactReference(
            artifact_id=ArtifactId(""),
            name="report",
            uri="file:///tmp/report",
        )


def test_artifact_reference_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="name"):
        ArtifactReference(
            artifact_id=ArtifactId("artifact"),
            name=" ",
            uri="file:///tmp/report",
        )


def test_artifact_reference_rejects_blank_uri() -> None:
    with pytest.raises(ValueError, match="uri"):
        ArtifactReference(
            artifact_id=ArtifactId("artifact"),
            name="report",
            uri="",
        )


def test_artifact_reference_rejects_blank_optional_text() -> None:
    with pytest.raises(ValueError, match="media_type"):
        ArtifactReference(
            artifact_id=ArtifactId("artifact"),
            name="report",
            uri="file:///tmp/report",
            media_type=" ",
        )


def test_artifact_reference_rejects_invalid_size_type() -> None:
    with pytest.raises(TypeError, match="size_bytes"):
        ArtifactReference(
            artifact_id=ArtifactId("artifact"),
            name="report",
            uri="file:///tmp/report",
            size_bytes=True,
        )


def test_artifact_reference_rejects_negative_size() -> None:
    with pytest.raises(ValueError, match="size_bytes"):
        ArtifactReference(
            artifact_id=ArtifactId("artifact-1"),
            name="report",
            uri="file:///tmp/report",
            size_bytes=-1,
        )


def test_external_run_ref_validates_and_freezes_metadata() -> None:
    source = {"region": "eu"}
    ref = ExternalRunRef(
        external_ref_id=ExternalRunRefId("ref-1"),
        provider="pyingestkit",
        external_run_id="job-123",
        uri="https://example.test/jobs/123",
        metadata=source,
    )

    source["region"] = "us"

    assert ref.metadata["region"] == "eu"


def test_external_run_ref_rejects_blank_reference_id() -> None:
    with pytest.raises(ValueError, match="external_ref_id"):
        ExternalRunRef(
            external_ref_id=ExternalRunRefId(""),
            provider="pyingestkit",
            external_run_id="job-123",
        )


@pytest.mark.parametrize(
    "provider,external_run_id",
    [("", "job"), (" ", "job"), ("provider", "")],
)
def test_external_run_ref_rejects_blank_required_fields(
    provider: str,
    external_run_id: str,
) -> None:
    with pytest.raises(ValueError):
        ExternalRunRef(
            external_ref_id=ExternalRunRefId("ref-1"),
            provider=provider,
            external_run_id=external_run_id,
        )


def test_external_run_ref_rejects_blank_optional_uri() -> None:
    with pytest.raises(ValueError, match="uri"):
        ExternalRunRef(
            external_ref_id=ExternalRunRefId("ref-1"),
            provider="provider",
            external_run_id="run",
            uri=" ",
        )


def test_workflow_parameter_requires_non_blank_name() -> None:
    with pytest.raises(ValueError, match="name"):
        WorkflowParameter(name=" ")


def test_workflow_parameter_preserves_declared_properties() -> None:
    parameter = WorkflowParameter(
        name="token",
        required=False,
        default="fallback",
        sensitive=True,
    )

    assert parameter.required is False
    assert parameter.default == "fallback"
    assert parameter.sensitive is True


def test_task_result_freezes_metadata_and_preserves_references() -> None:
    metadata = {"source": "test"}
    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact-1"),
        name="report",
        uri="file:///tmp/report",
    )
    external_ref = ExternalRunRef(
        external_ref_id=ExternalRunRefId("external-1"),
        provider="pyingestkit",
        external_run_id="run-1",
    )

    result = TaskResult(
        output={"ok": True},
        metadata=metadata,
        artifacts=(artifact,),
        external_refs=(external_ref,),
    )
    metadata["source"] = "changed"

    assert result.metadata["source"] == "test"
    assert result.artifacts == (artifact,)
    assert result.external_refs == (external_ref,)
