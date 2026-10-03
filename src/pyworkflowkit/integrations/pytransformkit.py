"""Canonical V2 PyTransformKit anti-corruption integration.

PyWorkflowKit owns workflow ordering, TaskRun/TaskAttempt identity, workload retry,
recovery and durable orchestration evidence. PyTransformKit owns transformation-plan
semantics, engine execution and provider-level retry. This module intentionally imports
no PyTransformKit package.
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
from pyworkflowkit.executors import TaskExecutionContext, TaskExecutionResult
from pyworkflowkit.plugins.v2 import V2WorkloadBinding
from pyworkflowkit.policies.retry import RetryPolicy
from pyworkflowkit.runtime import ExternalRunRef
from pyworkflowkit.runtime.evidence import normalize_json_value, plain_json_value

V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION = "1"
V2_PYTRANSFORMKIT_INTEGRATION_KEY = "pytransformkit"
V2_PYTRANSFORMKIT_REGISTRY_PREFIX = "pytransformkit:"

_PLAN_REF_PARAMETER = "pytransformkit.plan_ref"
_ENGINE_PARAMETER = "pytransformkit.engine"
_CREDENTIAL_REF_PARAMETER = "pytransformkit.credential_ref"
_RESERVED_PARAMETERS = frozenset(
    {
        _PLAN_REF_PARAMETER,
        _ENGINE_PARAMETER,
        _CREDENTIAL_REF_PARAMETER,
    }
)


class PyTransformKitExecutionStatus(StrEnum):
    """Normalized terminal PyTransformKit execution state."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    UNKNOWN_OUTCOME = "unknown_outcome"
    REQUIRES_RECONCILIATION = "requires_reconciliation"


@dataclass(frozen=True, slots=True)
class PyTransformKitResourceReference:
    """Dependency-free mirror of PyTransformKit ResourceReference."""

    scheme: str
    locator: str
    media_type: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    contract_version: str = V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.scheme, field_name="scheme")
        _require_text(self.locator, field_name="locator")
        if self.media_type is not None:
            _require_text(self.media_type, field_name="media_type")
        if self.contract_version != V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION:
            raise ValueError(
                f"unsupported PyTransformKit resource contract version {self.contract_version!r}"
            )
        object.__setattr__(
            self,
            "metadata",
            _normalize_pairs(self.metadata, field_name="metadata"),
        )

    def as_portable_output(self) -> dict[str, object]:
        """Return the strict JSON representation used for durable handoff."""

        return {
            "kind": "pytransformkit.resource_reference",
            "scheme": self.scheme,
            "locator": self.locator,
            "media_type": self.media_type,
            "metadata": {key: value for key, value in self.metadata},
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True, slots=True)
class PyTransformKitExecutionResult:
    """Normalized boundary result for one PyTransformKit TransformationExecution."""

    transformation_execution_id: str
    status: PyTransformKitExecutionStatus
    resource: PyTransformKitResourceReference | None = None
    engine_id: str | None = None
    plan_fingerprint: str | None = None
    status_locator: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    error_code: str | None = None
    provider_code: str | None = None
    message_summary: str | None = None
    retryable: bool = False
    contract_version: str = V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(
            self.transformation_execution_id,
            field_name="transformation_execution_id",
        )
        if not isinstance(self.status, PyTransformKitExecutionStatus):
            raise TypeError("status must be a PyTransformKitExecutionStatus")
        if self.resource is not None and not isinstance(
            self.resource,
            PyTransformKitResourceReference,
        ):
            raise TypeError("resource must be a PyTransformKitResourceReference or None")
        for name, value in (
            ("engine_id", self.engine_id),
            ("plan_fingerprint", self.plan_fingerprint),
            ("status_locator", self.status_locator),
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
    """Small sibling-owned wrapper contract used by PyWorkflowKit."""

    def run(
        self,
        *,
        context: TaskExecutionContext,
        inputs: Mapping[str, object],
    ) -> PyTransformKitExecutionResult:
        """Execute one complete transformation plan over portable inputs."""


class PyTransformKitWorkload(RegisteredWorkload):
    """Portable RegisteredWorkload for one PyTransformKit transformation plan."""

    integration_key = V2_PYTRANSFORMKIT_INTEGRATION_KEY

    def __init__(
        self,
        *,
        plan_ref: str,
        engine: str,
        parameters: tuple[tuple[str, str], ...] = (),
        credential_ref: str | None = None,
        executor_key: str = "inline",
        contract_version: str = V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION,
    ) -> None:
        _require_text(plan_ref, field_name="plan_ref")
        _require_text(engine, field_name="engine")
        if credential_ref is not None:
            _require_text(credential_ref, field_name="credential_ref")
        if contract_version != V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION:
            raise ValueError(
                f"unsupported PyTransformKit V2 integration contract version {contract_version!r}"
            )

        caller_parameters = _normalize_pairs(parameters, field_name="parameters")
        reserved = sorted(key for key, _ in caller_parameters if key in _RESERVED_PARAMETERS)
        if reserved:
            raise ValueError(
                "parameters cannot override reserved PyTransformKit keys: " + ", ".join(reserved)
            )

        integration_parameters = [
            *caller_parameters,
            (_PLAN_REF_PARAMETER, plan_ref),
            (_ENGINE_PARAMETER, engine),
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
    def engine(self) -> str:
        return dict(self.parameters)[_ENGINE_PARAMETER]

    @property
    def credential_ref(self) -> str | None:
        return dict(self.parameters).get(_CREDENTIAL_REF_PARAMETER)

    def fingerprint_payload(self) -> Mapping[str, object]:
        payload = dict(super().fingerprint_payload())
        payload.update(
            {
                "integration_key": self.integration_key,
                "plan_ref": self.plan_ref,
                "engine": self.engine,
                "credential_ref": self.credential_ref,
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class PyTransformKitWorkloadHandler:
    """Translate workflow inputs and PyTransformKit evidence into V2 runtime evidence."""

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
                        "PyTransformKitExecutionJob.run() must return PyTransformKitExecutionResult"
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
            if result.resource is None:  # pragma: no cover - DTO invariant
                raise RuntimeError("successful PyTransformKit result missing resource")
            return TaskExecutionResult(
                output=result.resource.as_portable_output(),
                external_runs=(external_ref,),
            )

        if result.status in {
            PyTransformKitExecutionStatus.UNKNOWN_OUTCOME,
            PyTransformKitExecutionStatus.REQUIRES_RECONCILIATION,
        }:
            return TaskExecutionResult(
                failure=_failure(
                    context=context,
                    error_code=result.error_code or "PYTRANSFORMKIT-UNKNOWN-OUTCOME",
                    category=FailureCategory.UNKNOWN_OUTCOME,
                    retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
                    uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
                    message_summary=(
                        result.message_summary or "PyTransformKit outcome requires reconciliation"
                    ),
                    provider_code=result.provider_code,
                    external_run=external_ref,
                    details=(("plan_ref", self.workload.plan_ref),),
                ),
                external_runs=(external_ref,),
            )

        if result.status is PyTransformKitExecutionStatus.CANCELLED:
            category = FailureCategory.EXTERNAL_PROVIDER
            retryability = Retryability.NON_RETRYABLE
        elif result.status is PyTransformKitExecutionStatus.TIMED_OUT:
            category = FailureCategory.TIMEOUT
            retryability = (
                Retryability.RETRYABLE if result.retryable else Retryability.NON_RETRYABLE
            )
        else:
            category = FailureCategory.EXTERNAL_PROVIDER
            retryability = (
                Retryability.RETRYABLE if result.retryable else Retryability.NON_RETRYABLE
            )

        return TaskExecutionResult(
            failure=_failure(
                context=context,
                error_code=result.error_code or "PYTRANSFORMKIT-FAILED",
                category=category,
                retryability=retryability,
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
    """Bind one transformation plan to the V2 RegisteredWorkload path."""

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
    engine: str,
    dependencies: tuple[str, ...] = (),
    parameters: tuple[tuple[str, str], ...] = (),
    retry_policy: RetryPolicy | None = None,
    credential_ref: str | None = None,
    executor_key: str = "inline",
) -> TaskDefinition:
    """Create one canonical task for one atomic PyTransformKit plan execution."""

    return TaskDefinition(
        key=key,
        workload=PyTransformKitWorkload(
            plan_ref=plan_ref,
            engine=engine,
            parameters=parameters,
            credential_ref=credential_ref,
            executor_key=executor_key,
        ),
        dependencies=dependencies,
        retry_policy=retry_policy or RetryPolicy(),
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
        "resource_reference_shape": ("scheme", "locator", "media_type", "metadata"),
        "external_reference_contract": "ExternalRunRef",
        "workload_retry_owner": "pyworkflowkit",
        "provider_retry_owner": "pytransformkit",
        "unknown_outcome_requires_reconciliation": True,
        "raw_credentials_supported": False,
        "credential_reference_supported": True,
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
    metadata["engine"] = result.engine_id or workload.engine
    if result.plan_fingerprint is not None:
        metadata["plan_fingerprint"] = result.plan_fingerprint
    if result.resource is not None:
        metadata["resource_scheme"] = result.resource.scheme
        metadata["resource_locator"] = result.resource.locator
    return ExternalRunRef(
        provider="pytransformkit",
        external_run_id=result.transformation_execution_id,
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
        source_component="pyworkflowkit.integrations.pytransformkit",
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
    "PyTransformKitWorkload",
    "PyTransformKitWorkloadHandler",
    "V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION",
    "V2_PYTRANSFORMKIT_INTEGRATION_KEY",
    "V2_PYTRANSFORMKIT_REGISTRY_PREFIX",
    "pytransformkit_v2_task",
    "pytransformkit_v2_workload_binding",
    "v2_pytransformkit_integration_snapshot",
]
