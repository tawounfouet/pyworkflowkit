"""Optional integration adapters that preserve core product boundaries."""

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
    "ExternalRetryOwner",
    "ExternalWorkload",
    "ExternalWorkloadAdapter",
    "ExternalWorkloadResult",
    "external_workload_task",
]
