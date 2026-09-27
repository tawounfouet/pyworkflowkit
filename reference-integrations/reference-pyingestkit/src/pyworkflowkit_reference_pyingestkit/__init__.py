"""Reference PyIngestKit adapter packaged outside pyworkflowkit core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyworkflowkit.integrations import ExternalWorkloadResult
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
)
from pyworkflowkit.ports.executor import RunContext


@dataclass(frozen=True, slots=True)
class PyIngestKitWorkload:
    """Adapt one real PyIngestKit Runner + Job pair to ExternalWorkload."""

    runner: Any
    job: Any

    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        del context
        result = self.runner.run(self.job)
        status = result.status.value
        succeeded = bool(result.succeeded)
        return ExternalWorkloadResult(
            external_run_id=result.run_id,
            succeeded=succeeded,
            output={
                "job_id": result.job_id,
                "job_version": result.job_version,
                "status": status,
            },
            uri=f"pyingestkit://runs/{result.run_id}",
            metadata={
                "job_id": result.job_id,
                "job_version": result.job_version,
                "status": status,
                "duration_seconds": result.duration_seconds,
                "warning_count": len(result.warnings),
                "adapter_package": "pyworkflowkit-reference-pyingestkit",
            },
            error_type=None if succeeded else "PyIngestKitRunFailed",
            error_message=None if succeeded else (result.error or "PyIngestKit run failed"),
            error_category=None if succeeded else "pyingestkit",
        )


class PyIngestKitAdapterFactory:
    """Create an ExternalWorkload from PyIngestKit public Runner/Job objects."""

    def wrap(self, *, runner: Any, job: Any) -> PyIngestKitWorkload:
        return PyIngestKitWorkload(runner=runner, job=job)


def plugin() -> RegisteredPlugin[PyIngestKitAdapterFactory]:
    """Return the workload plugin registration exposed through entry points."""

    return RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="pyingestkit-reference",
            plugin_type=PluginType.WORKLOAD,
            api_version=PLUGIN_API_VERSION,
            plugin_version="0.1.0",
            description="Reference adapter for the PyIngestKit public runtime API.",
        ),
        factory=PyIngestKitAdapterFactory,
    )


__all__ = ["PyIngestKitAdapterFactory", "PyIngestKitWorkload", "plugin"]
