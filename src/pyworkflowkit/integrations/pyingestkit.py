"""PyIngestKit workload adapter without a core dependency on PyIngestKit.

The adapter treats one PyIngestKit job as one atomic PyWorkflowKit task.
Concrete PyIngestKit packages can implement the small PyIngestKitJob protocol
outside this package and return the normalized PyIngestKitRunResult boundary DTO.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pyworkflowkit.declarative import TaskHandle
from pyworkflowkit.domain.ids import ExternalRunRefId, TaskId
from pyworkflowkit.domain.values import (
    ArtifactReference,
    ExternalRunRef,
    RetryPolicy,
    TaskResult,
)
from pyworkflowkit.errors import (
    PyIngestKitAdapterError,
    PyIngestKitRetryOwnershipError,
)
from pyworkflowkit.ports.executor import RunContext


class PyIngestKitRetryOwner(StrEnum):
    """Single owner of retry decisions across the integration boundary."""

    PYWORKFLOWKIT = "pyworkflowkit"
    PYINGESTKIT = "pyingestkit"


@dataclass(frozen=True, slots=True)
class PyIngestKitRunResult:
    """Normalized result expected from a PyIngestKit integration wrapper."""

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
        if not self.external_run_id.strip():
            raise ValueError("external_run_id must not be blank")
        if self.uri is not None and not self.uri.strip():
            raise ValueError("uri must not be blank when provided")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))

        if self.succeeded:
            if any(
                value is not None
                for value in (
                    self.error_type,
                    self.error_message,
                    self.error_category,
                )
            ):
                raise ValueError("successful PyIngestKitRunResult cannot define error fields")
        elif self.error_type is None:
            raise ValueError("failed PyIngestKitRunResult requires error_type")


@runtime_checkable
class PyIngestKitJob(Protocol):
    """Minimal anti-corruption contract implemented by an external wrapper."""

    def run(self, *, context: RunContext) -> PyIngestKitRunResult:
        """Execute one PyIngestKit job and normalize its result."""


@dataclass(frozen=True, slots=True)
class PyIngestKitTaskAdapter:
    """Translate one atomic PyIngestKit job execution into TaskResult."""

    job: PyIngestKitJob
    job_ref: str
    retry_owner: PyIngestKitRetryOwner = PyIngestKitRetryOwner.PYINGESTKIT

    def __post_init__(self) -> None:
        if not self.job_ref.strip():
            raise ValueError("job_ref must not be blank")

    def __call__(self, context: RunContext) -> TaskResult:
        try:
            result = self.job.run(context=context)
        except Exception as exc:
            raise PyIngestKitAdapterError(
                job_ref=self.job_ref,
                error_type=type(exc).__name__,
                error_message=str(exc) or type(exc).__name__,
                error_category=type(exc).__name__,
            ) from exc

        if not isinstance(result, PyIngestKitRunResult):
            raise PyIngestKitAdapterError(
                job_ref=self.job_ref,
                error_type="InvalidPyIngestKitResult",
                error_message="PyIngestKitJob.run() must return PyIngestKitRunResult",
                error_category="integration_contract",
            )

        if not result.succeeded:
            raise PyIngestKitAdapterError(
                job_ref=self.job_ref,
                error_type=result.error_type or "PyIngestKitJobFailed",
                error_message=result.error_message or result.error_type or "PyIngestKit job failed",
                error_category=result.error_category or result.error_type or "pyingestkit",
                external_run_id=result.external_run_id,
            )

        external_ref = ExternalRunRef(
            external_ref_id=ExternalRunRefId(
                f"pyingestkit:{context.task_run_id}:{result.external_run_id}"
            ),
            provider="pyingestkit",
            external_run_id=result.external_run_id,
            uri=result.uri,
            metadata={
                **result.metadata,
                "job_ref": self.job_ref,
                "retry_owner": self.retry_owner.value,
            },
        )
        return TaskResult(
            output=result.output,
            metadata={
                "pyingestkit_job_ref": self.job_ref,
                "retry_owner": self.retry_owner.value,
            },
            artifacts=result.artifacts,
            external_refs=(external_ref,),
        )


def pyingestkit_task(
    *,
    id: str,
    job_ref: str,
    job: PyIngestKitJob,
    depends_on: Sequence[TaskHandle | TaskId | str] = (),
    retry_owner: PyIngestKitRetryOwner = PyIngestKitRetryOwner.PYINGESTKIT,
    retry_policy: RetryPolicy | None = None,
    tags: Sequence[str] = (),
    description: str | None = None,
) -> TaskHandle:
    """Create one atomic PyWorkflowKit task backed by a PyIngestKit job."""

    policy = retry_policy or RetryPolicy()
    if retry_owner is PyIngestKitRetryOwner.PYINGESTKIT and policy.max_attempts != 1:
        raise PyIngestKitRetryOwnershipError(
            retry_owner=retry_owner.value,
            max_attempts=policy.max_attempts,
        )

    adapter = PyIngestKitTaskAdapter(
        job=job,
        job_ref=job_ref,
        retry_owner=retry_owner,
    )
    return TaskHandle(
        task_id=TaskId(id),
        handler_ref=f"pyingestkit:{job_ref}",
        handler=adapter,
        depends_on=tuple(_dependency_id(value) for value in depends_on),
        retry_policy=policy,
        executor_key="local",
        tags=frozenset(tags),
        description=description,
    )


def _dependency_id(value: TaskHandle | TaskId | str) -> TaskId:
    if isinstance(value, TaskHandle):
        return value.task_id
    return TaskId(str(value))


__all__ = [
    "PyIngestKitJob",
    "PyIngestKitRetryOwner",
    "PyIngestKitRunResult",
    "PyIngestKitTaskAdapter",
    "pyingestkit_task",
]
