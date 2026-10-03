"""PyIngestKit anti-corruption adapters for legacy 1.1 and canonical V2.

PyWorkflowKit treats one complete PyIngestKit ingestion job as one atomic workflow
workload. The core package never imports PyIngestKit and never expands the sibling
framework's internal acquire/RAW/parse/validate/profile/diff/publish lifecycle into the
PyWorkflowKit DAG.

The historical 1.1 adapter remains available unchanged. LOT-18 adds an additive V2
descriptor/binding contract based on RegisteredWorkload, TaskExecutionResult,
FailureEvidence and ExternalRunRef.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition
from pyworkflowkit.declarative import TaskHandle
from pyworkflowkit.diagnostics import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.domain.ids import ExternalRunRefId, TaskId
from pyworkflowkit.domain.values import ArtifactReference, TaskResult
from pyworkflowkit.domain.values import (
    ExternalRunRef as LegacyExternalRunRef,
)
from pyworkflowkit.domain.values import RetryPolicy as LegacyRetryPolicy
from pyworkflowkit.errors import (
    PyIngestKitAdapterError,
    PyIngestKitRetryOwnershipError,
)
from pyworkflowkit.executors import TaskExecutionContext, TaskExecutionResult
from pyworkflowkit.plugins.v2 import V2WorkloadBinding
from pyworkflowkit.policies.retry import RetryPolicy as V2RetryPolicy
from pyworkflowkit.ports.executor import RunContext
from pyworkflowkit.runtime import ExternalRunRef as V2ExternalRunRef

V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION = "1"
V2_PYINGESTKIT_REGISTRY_PREFIX = "pyingestkit:"
V2_PYINGESTKIT_INTEGRATION_KEY = "pyingestkit"

_V2_JOB_REF_PARAMETER = "pyingestkit.job_ref"
_V2_RETRY_OWNER_PARAMETER = "pyingestkit.retry_owner"
_V2_CREDENTIAL_REF_PARAMETER = "pyingestkit.credential_ref"
_V2_RESERVED_PARAMETERS = frozenset(
    {
        _V2_JOB_REF_PARAMETER,
        _V2_RETRY_OWNER_PARAMETER,
        _V2_CREDENTIAL_REF_PARAMETER,
    }
)


class PyIngestKitRetryOwner(StrEnum):
    """Single owner of retry decisions across the integration boundary."""

    PYWORKFLOWKIT = "pyworkflowkit"
    PYINGESTKIT = "pyingestkit"


@dataclass(frozen=True, slots=True)
class PyIngestKitRunResult:
    """Legacy 1.1 normalized result expected from a PyIngestKit wrapper."""

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
    """Legacy 1.1 anti-corruption contract implemented by an external wrapper."""

    def run(self, *, context: RunContext) -> PyIngestKitRunResult:
        """Execute one PyIngestKit job and normalize its result."""


@dataclass(frozen=True, slots=True)
class PyIngestKitTaskAdapter:
    """Legacy 1.1 adapter translating a PyIngestKit job into TaskResult."""

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

        external_ref = LegacyExternalRunRef(
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
    retry_policy: LegacyRetryPolicy | None = None,
    tags: Sequence[str] = (),
    description: str | None = None,
) -> TaskHandle:
    """Create one legacy 1.1 PyWorkflowKit task backed by a PyIngestKit job."""

    policy = retry_policy or LegacyRetryPolicy()
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


class PyIngestKitExecutionStatus(StrEnum):
    """Normalized V2 outcome reported by the PyIngestKit anti-corruption wrapper."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN_OUTCOME = "unknown_outcome"


@dataclass(frozen=True, slots=True)
class PyIngestKitExecutionResult:
    """Portable V2 result returned by one atomic PyIngestKit execution wrapper."""

    external_run_id: str
    status: PyIngestKitExecutionStatus
    output: object = None
    status_locator: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    error_code: str | None = None
    provider_code: str | None = None
    message_summary: str | None = None
    retryable: bool = False
    contract_version: str = V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_v2_text(self.external_run_id, field_name="external_run_id")
        if not isinstance(self.status, PyIngestKitExecutionStatus):
            raise TypeError("status must be a PyIngestKitExecutionStatus")
        if self.status_locator is not None:
            _require_v2_text(self.status_locator, field_name="status_locator")
        if self.error_code is not None:
            _require_v2_text(self.error_code, field_name="error_code")
        if self.provider_code is not None:
            _require_v2_text(self.provider_code, field_name="provider_code")
        if self.message_summary is not None:
            _require_v2_text(self.message_summary, field_name="message_summary")
        if not isinstance(self.retryable, bool):
            raise TypeError("retryable must be a bool")
        if self.contract_version != V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION:
            raise ValueError(
                f"unsupported PyIngestKit V2 integration contract version {self.contract_version!r}"
            )

        metadata = _normalize_v2_pairs(self.metadata, field_name="metadata")
        object.__setattr__(self, "metadata", metadata)

        if self.status is PyIngestKitExecutionStatus.SUCCEEDED:
            if self.error_code is not None or self.message_summary is not None:
                raise ValueError("successful PyIngestKitExecutionResult cannot define error fields")
        elif self.error_code is None:
            raise ValueError("failed or uncertain PyIngestKitExecutionResult requires error_code")


@runtime_checkable
class PyIngestKitExecutionJob(Protocol):
    """Minimal V2 sibling-owned job protocol; PyWorkflowKit imports no sibling package."""

    def run(self, *, context: TaskExecutionContext) -> PyIngestKitExecutionResult:
        """Execute one complete ingestion job and return normalized boundary evidence."""


class PyIngestKitWorkload(RegisteredWorkload):
    """Portable V2 RegisteredWorkload specialized for one PyIngestKit job."""

    integration_key = V2_PYINGESTKIT_INTEGRATION_KEY

    def __init__(
        self,
        *,
        job_ref: str,
        parameters: tuple[tuple[str, str], ...] = (),
        retry_owner: PyIngestKitRetryOwner = PyIngestKitRetryOwner.PYINGESTKIT,
        credential_ref: str | None = None,
        executor_key: str = "inline",
        contract_version: str = V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION,
    ) -> None:
        _require_v2_text(job_ref, field_name="job_ref")
        if not isinstance(retry_owner, PyIngestKitRetryOwner):
            raise TypeError("retry_owner must be a PyIngestKitRetryOwner")
        if credential_ref is not None:
            _require_v2_text(credential_ref, field_name="credential_ref")

        caller_parameters = _normalize_v2_pairs(parameters, field_name="parameters")
        reserved = sorted(key for key, _ in caller_parameters if key in _V2_RESERVED_PARAMETERS)
        if reserved:
            raise ValueError(
                "parameters cannot override reserved PyIngestKit keys: " + ", ".join(reserved)
            )

        integration_parameters = [
            *caller_parameters,
            (_V2_JOB_REF_PARAMETER, job_ref),
            (_V2_RETRY_OWNER_PARAMETER, retry_owner.value),
        ]
        if credential_ref is not None:
            integration_parameters.append((_V2_CREDENTIAL_REF_PARAMETER, credential_ref))

        super().__init__(
            registry_key=f"{V2_PYINGESTKIT_REGISTRY_PREFIX}{job_ref}",
            parameters=tuple(integration_parameters),
            executor_key=executor_key,
            contract_version=contract_version,
        )

    @property
    def job_ref(self) -> str:
        return dict(self.parameters)[_V2_JOB_REF_PARAMETER]

    @property
    def retry_owner(self) -> PyIngestKitRetryOwner:
        return PyIngestKitRetryOwner(dict(self.parameters)[_V2_RETRY_OWNER_PARAMETER])

    @property
    def credential_ref(self) -> str | None:
        return dict(self.parameters).get(_V2_CREDENTIAL_REF_PARAMETER)

    def fingerprint_payload(self) -> Mapping[str, object]:
        payload = dict(super().fingerprint_payload())
        payload.update(
            {
                "integration_key": self.integration_key,
                "job_ref": self.job_ref,
                "retry_owner": self.retry_owner.value,
                "credential_ref": self.credential_ref,
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class PyIngestKitWorkloadHandler:
    """Translate sibling-owned V2 execution evidence into canonical runtime evidence."""

    workload: PyIngestKitWorkload
    job: PyIngestKitExecutionJob

    def __post_init__(self) -> None:
        if not isinstance(self.workload, PyIngestKitWorkload):
            raise TypeError("workload must be a PyIngestKitWorkload")
        if not isinstance(self.job, PyIngestKitExecutionJob):
            raise TypeError("job must satisfy PyIngestKitExecutionJob")

    def __call__(self, context: TaskExecutionContext) -> TaskExecutionResult:
        if not isinstance(context, TaskExecutionContext):
            raise TypeError("context must be a TaskExecutionContext")

        try:
            result = self.job.run(context=context)
        except Exception as exc:
            return TaskExecutionResult(
                failure=_v2_failure(
                    context=context,
                    error_code="PWK-PYINGESTKIT-WRAPPER-EXCEPTION",
                    category=FailureCategory.CONTRACT_VIOLATION,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    message_summary=str(exc) or type(exc).__name__,
                    details=(
                        ("job_ref", self.workload.job_ref),
                        ("exception_type", type(exc).__name__),
                    ),
                )
            )

        if not isinstance(result, PyIngestKitExecutionResult):
            return TaskExecutionResult(
                failure=_v2_failure(
                    context=context,
                    error_code="PWK-PYINGESTKIT-RESULT-CONTRACT",
                    category=FailureCategory.CONTRACT_VIOLATION,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    message_summary=(
                        "PyIngestKitExecutionJob.run() must return PyIngestKitExecutionResult"
                    ),
                    details=(("job_ref", self.workload.job_ref),),
                )
            )

        external_ref = _v2_external_ref(
            workload=self.workload,
            result=result,
            context=context,
        )

        if result.status is PyIngestKitExecutionStatus.SUCCEEDED:
            return TaskExecutionResult(
                output=result.output,
                external_runs=(external_ref,),
            )

        if result.status is PyIngestKitExecutionStatus.UNKNOWN_OUTCOME:
            return TaskExecutionResult(
                failure=_v2_failure(
                    context=context,
                    error_code=result.error_code or "PYINGESTKIT-UNKNOWN-OUTCOME",
                    category=FailureCategory.UNKNOWN_OUTCOME,
                    retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
                    uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
                    message_summary=result.message_summary or "PyIngestKit outcome is uncertain",
                    provider_code=result.provider_code,
                    external_run=external_ref,
                    details=(("job_ref", self.workload.job_ref),),
                ),
                external_runs=(external_ref,),
            )

        return TaskExecutionResult(
            failure=_v2_failure(
                context=context,
                error_code=result.error_code or "PYINGESTKIT-FAILED",
                category=FailureCategory.EXTERNAL_PROVIDER,
                retryability=(
                    Retryability.RETRYABLE if result.retryable else Retryability.NON_RETRYABLE
                ),
                uncertainty=OutcomeUncertainty.KNOWN,
                message_summary=result.message_summary or "PyIngestKit job failed",
                provider_code=result.provider_code,
                external_run=external_ref,
                details=(("job_ref", self.workload.job_ref),),
            ),
            external_runs=(external_ref,),
        )


def pyingestkit_v2_workload_binding(
    *,
    workload: PyIngestKitWorkload,
    job: PyIngestKitExecutionJob,
) -> V2WorkloadBinding:
    """Return the explicit LOT-16 registry binding for one V2 PyIngestKit workload."""

    if not isinstance(workload, PyIngestKitWorkload):
        raise TypeError("workload must be a PyIngestKitWorkload")
    if not isinstance(job, PyIngestKitExecutionJob):
        raise TypeError("job must satisfy PyIngestKitExecutionJob")
    return V2WorkloadBinding(
        registry_key=workload.registry_key,
        handler=PyIngestKitWorkloadHandler(workload=workload, job=job),
    )


def pyingestkit_v2_task(
    *,
    key: str,
    job_ref: str,
    dependencies: tuple[str, ...] = (),
    parameters: tuple[tuple[str, str], ...] = (),
    retry_owner: PyIngestKitRetryOwner = PyIngestKitRetryOwner.PYINGESTKIT,
    retry_policy: V2RetryPolicy | None = None,
    credential_ref: str | None = None,
    executor_key: str = "inline",
) -> TaskDefinition:
    """Create one canonical V2 task representing one atomic PyIngestKit job."""

    policy = retry_policy or V2RetryPolicy()
    if retry_owner is PyIngestKitRetryOwner.PYINGESTKIT and policy.max_attempts != 1:
        raise PyIngestKitRetryOwnershipError(
            retry_owner=retry_owner.value,
            max_attempts=policy.max_attempts,
        )

    return TaskDefinition(
        key=key,
        workload=PyIngestKitWorkload(
            job_ref=job_ref,
            parameters=parameters,
            retry_owner=retry_owner,
            credential_ref=credential_ref,
            executor_key=executor_key,
        ),
        dependencies=dependencies,
        retry_policy=policy,
    )


def v2_pyingestkit_integration_snapshot() -> dict[str, object]:
    """Machine-readable LOT-18 boundary contract."""

    return {
        "contract_version": V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION,
        "integration_key": V2_PYINGESTKIT_INTEGRATION_KEY,
        "registry_prefix": V2_PYINGESTKIT_REGISTRY_PREFIX,
        "atomic_job_boundary": True,
        "imports_pyingestkit": False,
        "workload_base": "RegisteredWorkload",
        "binding_contract": "V2WorkloadBinding",
        "success_contract": "TaskExecutionResult",
        "failure_contract": "FailureEvidence",
        "external_reference_contract": "ExternalRunRef",
        "unknown_outcome_requires_reconciliation": True,
        "raw_credentials_supported": False,
        "credential_reference_supported": True,
        "implicit_retry_multiplication": False,
    }


def _v2_external_ref(
    *,
    workload: PyIngestKitWorkload,
    result: PyIngestKitExecutionResult,
    context: TaskExecutionContext,
) -> V2ExternalRunRef:
    metadata = {key: value for key, value in result.metadata if key != _V2_CREDENTIAL_REF_PARAMETER}
    metadata["job_ref"] = workload.job_ref
    metadata["retry_owner"] = workload.retry_owner.value
    return V2ExternalRunRef(
        provider="pyingestkit",
        external_run_id=result.external_run_id,
        kind="ingestion",
        status_hint=result.status.value,
        status_locator=result.status_locator,
        correlation_id=context.correlation.correlation_id,
        causation_id=context.correlation.causation_id,
        metadata=tuple(sorted(metadata.items())),
    )


def _v2_failure(
    *,
    context: TaskExecutionContext,
    error_code: str,
    category: FailureCategory,
    retryability: Retryability,
    uncertainty: OutcomeUncertainty,
    message_summary: str,
    provider_code: str | None = None,
    external_run: V2ExternalRunRef | None = None,
    details: tuple[tuple[str, str], ...] = (),
) -> FailureEvidence:
    return FailureEvidence(
        error_code=error_code,
        category=category,
        retryability=retryability,
        uncertainty=uncertainty,
        correlation_id=context.correlation.correlation_id,
        source_framework="pyingestkit",
        workflow_run_id=str(context.workflow_run_id),
        task_run_id=str(context.task_run_id),
        task_attempt_id=str(context.attempt_id),
        external_run=external_run,
        source_component="pyworkflowkit.integrations.pyingestkit.v2",
        provider_code=provider_code,
        message_summary=message_summary,
        details=details,
    )


def _require_v2_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    return value


def _normalize_v2_pairs(
    values: tuple[tuple[str, str], ...],
    *,
    field_name: str,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    normalized: dict[str, str] = {}
    for item in values:
        if (
            not isinstance(item, tuple)
            or len(item) != 2
            or not all(isinstance(value, str) for value in item)
        ):
            raise TypeError(f"{field_name} must contain string key/value pairs")
        key, value = item
        _require_v2_text(key, field_name=f"{field_name} key")
        if key in normalized:
            raise ValueError(f"{field_name} contains duplicate key {key!r}")
        normalized[key] = value
    return tuple(sorted(normalized.items()))


def _dependency_id(value: TaskHandle | TaskId | str) -> TaskId:
    if isinstance(value, TaskHandle):
        return value.task_id
    return TaskId(str(value))


__all__ = [
    "PyIngestKitExecutionJob",
    "PyIngestKitExecutionResult",
    "PyIngestKitExecutionStatus",
    "PyIngestKitJob",
    "PyIngestKitRetryOwner",
    "PyIngestKitRunResult",
    "PyIngestKitTaskAdapter",
    "PyIngestKitWorkload",
    "PyIngestKitWorkloadHandler",
    "V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION",
    "V2_PYINGESTKIT_INTEGRATION_KEY",
    "V2_PYINGESTKIT_REGISTRY_PREFIX",
    "pyingestkit_task",
    "pyingestkit_v2_task",
    "pyingestkit_v2_workload_binding",
    "v2_pyingestkit_integration_snapshot",
]
