"""Generic external-workload interoperability contract.

M47 defines the smallest synchronous boundary required to treat one execution owned by
another runtime as one atomic PyWorkflowKit task. The foreign runtime keeps ownership of
its internal lifecycle; PyWorkflowKit receives only a normalized result and portable
references.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pyworkflowkit.declarative import TaskHandle
from pyworkflowkit.domain.enums import TimeoutMode
from pyworkflowkit.domain.ids import ExternalRunRefId, TaskId
from pyworkflowkit.domain.values import (
    ArtifactReference,
    ExternalRunRef,
    RetryPolicy,
    TaskResult,
)
from pyworkflowkit.errors import (
    ExternalWorkloadError,
    ExternalWorkloadRetryOwnershipError,
)
from pyworkflowkit.ports.executor import RunContext

EXTERNAL_WORKLOAD_CONTRACT_VERSION = "1"


class ExternalRetryOwner(StrEnum):
    """Single retry authority across a nested runtime boundary."""

    PYWORKFLOWKIT = "pyworkflowkit"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class ExternalWorkloadResult:
    """Normalized boundary result returned by an external runtime wrapper."""

    external_run_id: str
    succeeded: bool
    output: object | None = None
    uri: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    artifacts: tuple[ArtifactReference, ...] = ()
    error_type: str | None = None
    error_message: str | None = None
    error_category: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.external_run_id, field_name="external_run_id")
        if self.uri is not None:
            _require_text(self.uri, field_name="uri")
        if self.error_type is not None:
            _require_text(self.error_type, field_name="error_type")
        if self.error_message is not None:
            _require_text(self.error_message, field_name="error_message")
        if self.error_category is not None:
            _require_text(self.error_category, field_name="error_category")

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))

        error_fields = (self.error_type, self.error_message, self.error_category)
        if self.succeeded and any(value is not None for value in error_fields):
            raise ValueError("successful ExternalWorkloadResult cannot define error fields")
        if not self.succeeded and self.error_type is None:
            raise ValueError("failed ExternalWorkloadResult requires error_type")


@runtime_checkable
class ExternalWorkload(Protocol):
    """Minimal protocol implemented by a wrapper around one foreign runtime workload."""

    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        """Execute one external workload and return its normalized boundary result."""


@dataclass(frozen=True, slots=True)
class ExternalWorkloadAdapter:
    """Translate one external workload execution into a PyWorkflowKit TaskResult."""

    workload: ExternalWorkload
    provider: str
    workload_ref: str
    retry_owner: ExternalRetryOwner = ExternalRetryOwner.EXTERNAL

    def __post_init__(self) -> None:
        _require_text(self.provider, field_name="provider")
        _require_text(self.workload_ref, field_name="workload_ref")
        if not isinstance(self.retry_owner, ExternalRetryOwner):
            raise TypeError("retry_owner must be an ExternalRetryOwner")

    def __call__(self, context: RunContext) -> TaskResult:
        try:
            result = self.workload.run(context=context)
        except ExternalWorkloadError:
            raise
        except Exception as exc:
            raise ExternalWorkloadError(
                provider=self.provider,
                workload_ref=self.workload_ref,
                error_type=type(exc).__name__,
                error_message=str(exc) or type(exc).__name__,
                error_category=type(exc).__name__,
            ) from exc

        if not isinstance(result, ExternalWorkloadResult):
            raise ExternalWorkloadError(
                provider=self.provider,
                workload_ref=self.workload_ref,
                error_type="InvalidExternalWorkloadResult",
                error_message="ExternalWorkload.run() must return ExternalWorkloadResult",
                error_category="integration_contract",
            )

        if not result.succeeded:
            raise ExternalWorkloadError(
                provider=self.provider,
                workload_ref=self.workload_ref,
                error_type=result.error_type or "ExternalWorkloadFailed",
                error_message=(
                    result.error_message or result.error_type or "external workload failed"
                ),
                error_category=result.error_category or result.error_type or "external_workload",
                external_run_id=result.external_run_id,
            )

        return _success_result_to_task_result(
            result=result,
            context=context,
            provider=self.provider,
            workload_ref=self.workload_ref,
            retry_owner=self.retry_owner,
        )


def external_workload_task(
    *,
    id: str,
    provider: str,
    workload_ref: str,
    workload: ExternalWorkload,
    depends_on: Sequence[TaskHandle | TaskId | str] = (),
    retry_owner: ExternalRetryOwner = ExternalRetryOwner.EXTERNAL,
    retry_policy: RetryPolicy | None = None,
    executor_key: str = "local",
    timeout_seconds: float | None = None,
    timeout_mode: TimeoutMode = TimeoutMode.NONE,
    tags: Sequence[str] = (),
    description: str | None = None,
) -> TaskHandle:
    """Create one atomic task backed by an execution owned by another runtime."""

    _require_text(id, field_name="id")
    _require_text(provider, field_name="provider")
    _require_text(workload_ref, field_name="workload_ref")
    _require_text(executor_key, field_name="executor_key")
    if not isinstance(retry_owner, ExternalRetryOwner):
        raise TypeError("retry_owner must be an ExternalRetryOwner")

    policy = retry_policy or RetryPolicy()
    if retry_owner is ExternalRetryOwner.EXTERNAL and policy.max_attempts != 1:
        raise ExternalWorkloadRetryOwnershipError(
            provider=provider,
            workload_ref=workload_ref,
            retry_owner=retry_owner.value,
            max_attempts=policy.max_attempts,
        )

    adapter = ExternalWorkloadAdapter(
        workload=workload,
        provider=provider,
        workload_ref=workload_ref,
        retry_owner=retry_owner,
    )
    return TaskHandle(
        task_id=TaskId(id),
        handler_ref=f"external:{provider}:{workload_ref}:{id}",
        handler=adapter,
        depends_on=tuple(_dependency_id(value) for value in depends_on),
        retry_policy=policy,
        executor_key=executor_key,
        timeout_seconds=timeout_seconds,
        timeout_mode=timeout_mode,
        tags=frozenset(tags),
        description=description,
    )


def _success_result_to_task_result(
    *,
    result: ExternalWorkloadResult,
    context: RunContext,
    provider: str,
    workload_ref: str,
    retry_owner: ExternalRetryOwner,
) -> TaskResult:
    external_ref = ExternalRunRef(
        external_ref_id=ExternalRunRefId(
            f"{provider}:{context.task_run_id}:{result.external_run_id}"
        ),
        provider=provider,
        external_run_id=result.external_run_id,
        uri=result.uri,
        metadata={
            **result.metadata,
            "workload_ref": workload_ref,
            "retry_owner": retry_owner.value,
        },
    )
    return TaskResult(
        output=result.output,
        metadata={
            "external_workload_provider": provider,
            "external_workload_ref": workload_ref,
            "retry_owner": retry_owner.value,
        },
        artifacts=result.artifacts,
        external_refs=(external_ref,),
    )


def _dependency_id(value: TaskHandle | TaskId | str) -> TaskId:
    if isinstance(value, TaskHandle):
        return value.task_id
    return TaskId(str(value))


def _require_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    return value


__all__ = [
    "EXTERNAL_WORKLOAD_CONTRACT_VERSION",
    "ExternalRetryOwner",
    "ExternalWorkload",
    "ExternalWorkloadAdapter",
    "ExternalWorkloadResult",
    "external_workload_task",
]
