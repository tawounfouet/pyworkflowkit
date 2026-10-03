"""Canonical V2 PyTransformKit anti-corruption integration.

PyWorkflowKit owns workflow ordering, attempt identity, retry/recovery and durable
evidence. PyTransformKit owns transformation-plan semantics and transformation
execution. This module intentionally imports no PyTransformKit package.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition
from pyworkflowkit.diagnostics import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.errors import PyTransformKitRetryOwnershipError
from pyworkflowkit.executors import TaskExecutionContext, TaskExecutionResult
from pyworkflowkit.plugins.v2 import V2WorkloadBinding
from pyworkflowkit.policies.retry import RetryPolicy
from pyworkflowkit.runtime import ExternalRunRef, normalize_json_value, plain_json_value

V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION = "1"
V2_PYTRANSFORMKIT_INTEGRATION_KEY = "pytransformkit"
V2_PYTRANSFORMKIT_REGISTRY_PREFIX = "pytransformkit:"

_PLAN_REF_PARAMETER = "pytransformkit.plan_ref"
_RETRY_OWNER_PARAMETER = "pytransformkit.retry_owner"
_CREDENTIAL_REF_PARAMETER = "pytransformkit.credential_ref"
_RESERVED_PARAMETERS = frozenset(
    {
        _PLAN_REF_PARAMETER,
        _RETRY_OWNER_PARAMETER,
        _CREDENTIAL_REF_PARAMETER,
    }
)


class PyTransformKitRetryOwner(StrEnum):
    """Single owner of workload-level retry across the sibling boundary."""

    PYWORKFLOWKIT = "pyworkflowkit"
    PYTRANSFORMKIT = "pytransformkit"


class PyTransformKitExecutionStatus(StrEnum):
    """Normalized sibling execution disposition."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN_OUTCOME = "unknown_outcome"


@dataclass(frozen=True, slots=True)
class PyTransformKitResourceReference:
    """Portable anti-corruption reference to a transformation-owned resource."""

    resource_id: str
    uri: str
    version: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    contract_version: str = V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.resource_id, field_name="resource_id")
        _require_text(self.uri, field_name="uri")
        if self.version is not None:
            _require_text(self.version, field_name="version")
        if self.contract_version != V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION:
            raise ValueError(
                "unsupported PyTransformKit resource contract version "
                f"{self.contract_version!r}"
            )
        object.__setattr__(
            self,
            "metadata",
            _normalize_pairs(self.metadata, field_name="metadata"),
        )

    def as_portable_output(self) -> dict[str, object]:
        """Return strict JSON-portable output suitable for durable checkpointing."""

        return {
            "kind": "pytransformkit.resource_reference",
            "resource_id": self.resource_id,
            "uri": self.uri,
            "version": self.version,
            "metadata": {key: value for key, value in self.metadata},
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True, slots=True)
class PyTransformKitExecutionResult:
    """Normalized result returned by one transformation wrapper."""

    external_run_id: str
    status: PyTransformKitExecutionStatus
    resource: PyTransformKitResourceReference | None = None
    status_locator: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    error_code: str | None = None
    provider_code: str | None = None
    message_summary: str | None = None
    retryable: bool = False
    contract_version: str = V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.external_run_id, field_name="external_run_id")
        if not isinstance(self.status, PyTransformKitExecutionStatus):
            raise TypeError("status must be a PyTransformKitExecutionStatus")
        if self.resource is not None and not isinstance(
            self.resource,
            PyTransformKitResourceReference,
        ):
            raise TypeError("resource must be a PyTransformKitResourceReference or None")
        if self.status_locator is not None:
            _require_text(self.status_locator, field_name="status_locator")
        for name, value in (
            ("error_code", self.error_code),
            ("provider_code", self.provider_code),
            ("message_summary", self.message_summary),
        ):
            if value is not None:
                _require_text(value, field_name=name)
        if not isinstance(self.retryable, bool):
            raise TypeError("retryable must be a bool")
        if self.contract_version != V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION:
            raise ValueError(
                "unsupported PyTransformKit V2 integration contract version "
                f"{self.contract_version!r}"
            )
        object.__setattr__(
            self,
            "metadata",
            _normalize_pairs(self.metadata, field_name="metadata"),
        )

        if self.status is PyTransformKitExecutionStatus.SUCCEEDED:
            if self.resource is None:
                raise ValueError("successful PyTransformKitExecutionResult requires resource")
            if self.error_code is not None or self.message_summary is not None:
                raise ValueError(
                    "successful PyTransformKitExecutionResult cannot define error fields"
                )
        elif self.error_code is None:
            raise ValueError(
                "failed or uncertain PyTransformKitExecutionResult requires error_code"
            )


@runtime_checkable
class PyTransformKitExecutionJob(Protocol):
    """Minimal sibling-owned transformation protocol."""

    def run(
        self,
        *,
        context: TaskExecutionContext,
        inputs: Mapping[str, object],
    ) -> PyTransformKitExecutionResult:
        """Execute one complete transformation plan over portable dependency inputs."""


class PyTransformKitWorkload(RegisteredWorkload):
    """Portable V2 workload descriptor for one PyTransformKit transformation plan."""

    integration_key = V2_PYTRANSFORMKIT_INTEGRATION_KEY

    def __init__(
        self,
        *,
        plan_ref: str,
        parameters: tuple[tuple[str, str], ...] = (),
        retry_owner: PyTransformKitRetryOwner = PyTransformKitRetryOwner.PYTRANSFORMKIT,
        credential_ref: str | None = None,
        executor_key: str = "inline",
        contract_version: str = V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION,
    ) -> None:
        _require_text(plan_ref, field_name="plan_ref")
        if not isinstance(retry_owner, PyTransformKitRetryOwner):
            raise TypeError("retry_owner must be a PyTransformKitRetryOwner")
        if credential_ref is not None:
            _require_text(credential_ref, field_name="credential_ref")

        caller_parameters = _normalize_pairs(parameters, field_name="parameters")
        reserved = sorted(key for key, _ in caller_parameters if key in _RESERVED_PARAMETERS)
        if reserved:
            raise ValueError(
                "parameters cannot override reserved PyTransformKit keys: "
                + ", ".join(reserved)
            )

        integration_parameters = [
            *caller_parameters,
            (_PLAN_REF_PARAMETER, plan_ref),
            (_RETRY_OWNER_PARAMETER, retry_owner.value),
        ]
        if credential_ref is not None:
            integration_parameters.append((_CREDENTIAL_REF_PARAMETER, credential_ref))

        super().__init__(
            registry_key=f"{V2_PYTRANSFORMKIT_REGISTRY_PREFIX}{plan_ref}",
            parameters=tuple(integration_parameters),
            executor_key=executor_key,
            contract_version=contract_version,
        )

    @property
    def plan_ref(self) -> str:
        return dict(self.parameters)[_PLAN_REF_PARAMETER]

    @property
    def retry_owner(self) -> PyTransformKitRetryOwner:
        return PyTransformKitRetryOwner(dict(self.parameters)[_RETRY_OWNER_PARAMETER])

    @property
    def credential_ref(self) -> str | None:
        return dict(self.parameters).get(_CREDENTIAL_REF_PARAMETER)

    def fingerprint_payload(self) -> Mapping[str, object]:
        payload = dict(super().fingerprint_payload())
        payload.update(
            {
                "integration_key": self.integration_key,
                "plan_ref": self.plan_ref,
                "retry_owner": self.retry_owner.value,
                "credential_ref": self.credential_ref,
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class PyTransformKitWorkloadHandler:
    """Translate portable workflow inputs and sibling evidence into V2 runtime evidence."""

    workload: PyTransformKitWorkload
    job: PyTransformKitExecutionJob

    def __post_init__(self) -> None:
        if not isinstance(self.workload, PyTransformKitWorkload):
            raise TypeError("workload must be a PyTransformKitWorkload")
        if not isinstance(self.job, PyTransformKitExecutionJob):
            raise TypeError("job must satisfy PyTransformKitExecutionJob")

    def __call__(self, context: TaskExecutionContext) -> TaskExecutionResult:
        if not isinstance(context, TaskExecutionContext):
            raise TypeError("context must be a TaskExecutionContext")

        try:
            inputs = _portable_inputs(context.dependency_outputs)
        except (TypeError, ValueError) as exc:
            return TaskExecutionResult(
                failure=_failure(
                    context=context,
                    error_code="PWK-PYTRANSFORMKIT-NONPORTABLE-INPUT",
                    category=FailureCategory.CONTRACT_VIOLATION,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    message_summary=str(exc),
                    details=(("plan_ref", self.workload.plan_ref),),
                )
            )

        try:
            result = self.job.run(context=context, inputs=inputs)
        except Exception as exc:
            return TaskExecutionResult(
                failure=_failure(
                    context=context,
                    error_code="PWK-PYTRANSFORMKIT-WRAPPER-EXCEPTION",
                    category=FailureCategory.CONTRACT_VIOLATION,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    message_summary=str(exc) or type(exc).__name__,
                    details=(
                        ("plan_ref", self.workload.plan_ref),
                        ("exception_type", type(exc).__name__),
                    ),
                )
            )

        if not isinstance(result, PyTransformKitExecutionResult):
            return TaskExecutionResult(
                failure=_failure(
                    context=context,
                    error_code="PWK-PYTRANSFORMKIT-RESULT-CONTRACT",
                    category=FailureCategory.CONTRACT_VIOLATION,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    message_summary=(
                        "PyTransformKitExecutionJob.run() must return "
                        "PyTransformKitExecutionResult"
                    ),
                    details=(("plan_ref", self.workload.plan_ref),),
                )
            )

        external_ref = _external_ref(
            workload=self.workload,
            result=result,
            context=context,
        )

        if result.status is PyTransformKitExecutionStatus.SUCCEEDED:
            if result.resource is None:  # pragma: no cover - guarded by DTO invariant
                raise RuntimeError("successful PyTransformKit result missing resource")
            return TaskExecutionResult(
                output=result.resource.as_portable_output(),
                external_runs=(external_ref,),
            )

        if result.status is PyTransformKitExecutionStatus.UNKNOWN_OUTCOME:
            return TaskExecutionResult(
                failure=_failure(
                    context=context,
                    error_code=result.error_code or "PYTRANSFORMKIT-UNKNOWN-OUTCOME",
                    category=FailureCategory.UNKNOWN_OUTCOME,
                    retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
                    uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
                    message_summary=(
                        result.message_summary or "PyTransformKit outcome is uncertain"
                    ),
                    provider_code=result.provider_code,
                    external_run=external_ref,
                    details=(("plan_ref", self.workload.plan_ref),),
                ),
                external_runs=(external_ref,),
            )

        return TaskExecutionResult(
            failure=_failure(
                context=context,
                error_code=result.error_code or "PYTRANSFORMKIT-FAILED",
                category=FailureCategory.EXTERNAL_PROVIDER,
                retryability=(
                    Retryability.RETRYABLE if result.retryable else Retryability.NON_RETRYABLE
                ),
                uncertainty=OutcomeUncertainty.KNOWN,
                message_summary=result.message_summary or "PyTransformKit transformation failed",
                provider_code=result.provider_code,
                external_run=external_ref,
                details=(("plan_ref", self.workload.plan_ref),),
            ),
            external_runs=(external_ref,),
        )


def pytransformkit_v2_workload_binding(
    *,
    workload: PyTransformKitWorkload,
    job: PyTransformKitExecutionJob,
) -> V2WorkloadBinding:
    """Bind one transformation plan to the canonical V2 registered-workload path."""

    if not isinstance(workload, PyTransformKitWorkload):
        raise TypeError("workload must be a PyTransformKitWorkload")
    if not isinstance(job, PyTransformKitExecutionJob):
        raise TypeError("job must satisfy PyTransformKitExecutionJob")
    return V2WorkloadBinding(
        registry_key=workload.registry_key,
        handler=PyTransformKitWorkloadHandler(workload=workload, job=job),
    )


def pytransformkit_v2_task(
    *,
    key: str,
    plan_ref: str,
    dependencies: tuple[str, ...] = (),
    parameters: tuple[tuple[str, str], ...] = (),
    retry_owner: PyTransformKitRetryOwner = PyTransformKitRetryOwner.PYTRANSFORMKIT,
    retry_policy: RetryPolicy | None = None,
    credential_ref: str | None = None,
    executor_key: str = "inline",
) -> TaskDefinition:
    """Create one canonical V2 task representing one atomic transformation plan."""

    policy = retry_policy or RetryPolicy()
    if retry_owner is PyTransformKitRetryOwner.PYTRANSFORMKIT and policy.max_attempts != 1:
        raise PyTransformKitRetryOwnershipError(
            retry_owner=retry_owner.value,
            max_attempts=policy.max_attempts,
        )

    return TaskDefinition(
        key=key,
        workload=PyTransformKitWorkload(
            plan_ref=plan_ref,
            parameters=parameters,
            retry_owner=retry_owner,
            credential_ref=credential_ref,
            executor_key=executor_key,
        ),
        dependencies=dependencies,
        retry_policy=policy,
    )


def v2_pytransformkit_integration_snapshot() -> dict[str, object]:
    """Machine-readable LOT-19 integration contract."""

    return {
        "contract_version": V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION,
        "integration_key": V2_PYTRANSFORMKIT_INTEGRATION_KEY,
        "registry_prefix": V2_PYTRANSFORMKIT_REGISTRY_PREFIX,
        "atomic_plan_boundary": True,
        "imports_pytransformkit": False,
        "workload_base": "RegisteredWorkload",
        "binding_contract": "V2WorkloadBinding",
        "portable_dependency_handoff": True,
        "resource_reference_output": True,
        "external_reference_contract": "ExternalRunRef",
        "unknown_outcome_requires_reconciliation": True,
        "raw_credentials_supported": False,
        "credential_reference_supported": True,
        "implicit_retry_multiplication": False,
    }


def _portable_inputs(values: Mapping[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key in sorted(values):
        _require_text(key, field_name="dependency output key")
        normalized_value = normalize_json_value(
            values[key],
            path=f"dependency_outputs.{key}",
        )
        normalized[key] = plain_json_value(normalized_value)
    return normalized


def _external_ref(
    *,
    workload: PyTransformKitWorkload,
    result: PyTransformKitExecutionResult,
    context: TaskExecutionContext,
) -> ExternalRunRef:
    metadata = {key: value for key, value in result.metadata if key != _CREDENTIAL_REF_PARAMETER}
    metadata["plan_ref"] = workload.plan_ref
    metadata["retry_owner"] = workload.retry_owner.value
    return ExternalRunRef(
        provider="pytransformkit",
        external_run_id=result.external_run_id,
        kind="transformation_execution",
        status_hint=result.status.value,
        status_locator=result.status_locator,
        correlation_id=context.correlation.correlation_id,
        causation_id=context.correlation.causation_id,
        metadata=tuple(sorted(metadata.items())),
    )


def _failure(
    *,
    context: TaskExecutionContext,
    error_code: str,
    category: FailureCategory,
    retryability: Retryability,
    uncertainty: OutcomeUncertainty,
    message_summary: str,
    provider_code: str | None = None,
    external_run: ExternalRunRef | None = None,
    details: tuple[tuple[str, str], ...] = (),
) -> FailureEvidence:
    return FailureEvidence(
        error_code=error_code,
        category=category,
        retryability=retryability,
        uncertainty=uncertainty,
        correlation_id=context.correlation.correlation_id,
        source_framework="pytransformkit",
        workflow_run_id=str(context.workflow_run_id),
        task_run_id=str(context.task_run_id),
        task_attempt_id=str(context.attempt_id),
        external_run=external_run,
        source_component="pyworkflowkit.integrations.pytransformkit.v2",
        provider_code=provider_code,
        message_summary=message_summary,
        details=details,
    )


def _require_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    return value


def _normalize_pairs(
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
        _require_text(key, field_name=f"{field_name} key")
        if key in normalized:
            raise ValueError(f"{field_name} contains duplicate key {key!r}")
        normalized[key] = value
    return tuple(sorted(normalized.items()))


__all__ = [
    "PyTransformKitExecutionJob",
    "PyTransformKitExecutionResult",
    "PyTransformKitExecutionStatus",
    "PyTransformKitResourceReference",
    "PyTransformKitRetryOwner",
    "PyTransformKitWorkload",
    "PyTransformKitWorkloadHandler",
    "V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION",
    "V2_PYTRANSFORMKIT_INTEGRATION_KEY",
    "V2_PYTRANSFORMKIT_REGISTRY_PREFIX",
    "pytransformkit_v2_task",
    "pytransformkit_v2_workload_binding",
    "v2_pytransformkit_integration_snapshot",
]
