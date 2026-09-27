"""Optional integration adapters that preserve core product boundaries."""

from pyworkflowkit.contracts.references import (
    REFERENCE_INTEROPERABILITY_CONTRACT_VERSION,
    normalize_reference_metadata,
    validate_portable_artifact_reference,
    validate_portable_external_run_ref,
    validate_provider_name,
    validate_reference_uri,
)
from pyworkflowkit.integrations.workload import (
    EXTERNAL_WORKLOAD_CONTRACT_VERSION,
    ExternalRetryOwner,
    ExternalWorkload,
    ExternalWorkloadAdapter,
    ExternalWorkloadResult,
    external_workload_task,
)

__all__ = [
    "EXTERNAL_WORKLOAD_CONTRACT_VERSION",
    "REFERENCE_INTEROPERABILITY_CONTRACT_VERSION",
    "ExternalRetryOwner",
    "ExternalWorkload",
    "ExternalWorkloadAdapter",
    "ExternalWorkloadResult",
    "external_workload_task",
    "normalize_reference_metadata",
    "validate_portable_artifact_reference",
    "validate_portable_external_run_ref",
    "validate_provider_name",
    "validate_reference_uri",
]
