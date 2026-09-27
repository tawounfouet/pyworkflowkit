"""Machine-readable developer-experience contracts for PyWorkflowKit."""

from __future__ import annotations

DX_CONTRACT_VERSION = "1"
DX_TARGET_RELEASE = "1.0.0"

GETTING_STARTED_GUIDES: tuple[str, ...] = (
    "docs/guides/getting-started.md",
    "docs/guides/cli-workflow.md",
    "docs/guides/failures-and-retries.md",
    "docs/guides/persistence-and-evidence.md",
    "docs/guides/plugin-authoring.md",
    "docs/guides/troubleshooting.md",
)

EXECUTABLE_EXAMPLES: tuple[str, ...] = (
    "examples/00_hello_world.py",
    "examples/01_failure_and_retry.py",
    "examples/02_sqlite_persistence.py",
    "examples/03_ecosystem_plugin.py",
    "examples/getting_started_workflow.py",
)

PUBLIC_AUTHORING_FACADES: tuple[str, ...] = (
    "pyworkflowkit",
    "pyworkflowkit.ecosystem",
)

CLI_FIRST_RUN_COMMANDS: tuple[str, ...] = (
    "version",
    "validate",
    "plan",
    "run",
    "inspect",
    "events",
    "manifest",
)


def developer_experience_contract_snapshot() -> dict[str, object]:
    """Return deterministic RQ-04 documentation and first-use metadata."""

    return {
        "contract_version": DX_CONTRACT_VERSION,
        "target_release": DX_TARGET_RELEASE,
        "guides": list(GETTING_STARTED_GUIDES),
        "examples": list(EXECUTABLE_EXAMPLES),
        "public_authoring_facades": list(PUBLIC_AUTHORING_FACADES),
        "cli_first_run_commands": list(CLI_FIRST_RUN_COMMANDS),
    }


DX_V2_CONTRACT_VERSION = "2"
DX_V2_TARGET_RELEASE = "1.1.0"

DX_V2_REQUIRED_SURFACES: tuple[str, ...] = (
    "cli",
    "guides",
    "examples",
    "notebooks",
    "tests",
)

DX_V2_PUBLIC_AUTHORING_FACADES: tuple[str, ...] = (
    "pyworkflowkit",
    "pyworkflowkit.ecosystem",
    "pyworkflowkit.control_plane",
    "pyworkflowkit.integrations",
)

DX_V2_CLI_COMMANDS: tuple[str, ...] = (
    "version",
    "validate",
    "plan",
    "run",
    "inspect",
    "events",
    "manifest",
    "plugins",
    "doctor",
)

DX_V2_CANONICAL_GUIDES: tuple[str, ...] = (
    "docs/guides/00_ZERO_TO_HERO.md",
    "docs/guides/01_INSTALLATION_AND_FIRST_WORKFLOW.md",
    "docs/guides/02_TASKS_AND_HANDLERS.md",
    "docs/guides/03_WORKFLOW_DEFINITIONS.md",
    "docs/guides/04_DEPENDENCIES_AND_DAG.md",
    "docs/guides/05_EXECUTION_PLANNING.md",
    "docs/guides/06_WORKFLOW_RUNTIME.md",
    "docs/guides/07_RUN_CONTEXT_AND_DATA_FLOW.md",
    "docs/guides/08_FAILURES_AND_RETRIES.md",
    "docs/guides/09_EVENTS_AND_OBSERVABILITY.md",
    "docs/guides/10_MANIFEST_AND_EVIDENCE.md",
    "docs/guides/11_METADATA_STORE.md",
    "docs/guides/12_SQLITE_PERSISTENCE.md",
    "docs/guides/13_POSTGRESQL_PERSISTENCE.md",
    "docs/guides/14_CONFIGURATION.md",
    "docs/guides/15_CLI_ZERO_TO_HERO.md",
    "docs/guides/16_CONCURRENCY.md",
    "docs/guides/17_TIMEOUTS_AND_CANCELLATION.md",
    "docs/guides/18_EXECUTORS.md",
    "docs/guides/19_PLUGINS_AND_ECOSYSTEM.md",
    "docs/guides/20_EXTERNAL_WORKLOADS.md",
    "docs/guides/21_CUSTOM_EXECUTOR.md",
    "docs/guides/22_CUSTOM_METADATA_STORE.md",
    "docs/guides/23_CONTROL_PLANE.md",
    "docs/guides/24_PYINGESTKIT_INTEGRATION.md",
    "docs/guides/25_TESTING_WORKFLOWS.md",
    "docs/guides/26_DEBUGGING_AND_TROUBLESHOOTING.md",
    "docs/guides/27_PRODUCTION_PATTERNS.md",
    "docs/guides/99_COMPLETE_REFERENCE_APPLICATION.md",
)

DX_V2_CANONICAL_EXAMPLES: tuple[str, ...] = (
    "examples/00_hello_world.py",
    "examples/01_tasks_and_handlers.py",
    "examples/02_workflow_definitions.py",
    "examples/03_dependencies.py",
    "examples/04_dag.py",
    "examples/05_execution_plan.py",
    "examples/06_runtime.py",
    "examples/07_run_context.py",
    "examples/08_failure.py",
    "examples/09_retry.py",
    "examples/10_events.py",
    "examples/11_manifest.py",
    "examples/12_sqlite.py",
    "examples/13_postgresql.py",
    "examples/14_configuration.py",
    "examples/15_concurrency.py",
    "examples/16_timeout.py",
    "examples/17_cancellation.py",
    "examples/18_external_workload.py",
    "examples/19_plugin.py",
    "examples/20_custom_executor.py",
    "examples/21_control_plane.py",
    "examples/integrations/pyingestkit/atomic_job.py",
    "examples/complete/data_pipeline.py",
)

DX_V2_CANONICAL_NOTEBOOKS: tuple[str, ...] = (
    "notebooks/00 - Environment and Setup.ipynb",
    "notebooks/01 - Hello Workflow.ipynb",
    "notebooks/02 - Tasks and Handlers.ipynb",
    "notebooks/03 - Workflow Definitions.ipynb",
    "notebooks/04 - Dependencies and DAG.ipynb",
    "notebooks/05 - Execution Planning.ipynb",
    "notebooks/06 - Workflow Runtime.ipynb",
    "notebooks/07 - RunContext and Data Flow.ipynb",
    "notebooks/08 - Failures and Retries.ipynb",
    "notebooks/09 - Events and Evidence.ipynb",
    "notebooks/10 - Run Manifest.ipynb",
    "notebooks/11 - SQLite Persistence.ipynb",
    "notebooks/12 - Configuration.ipynb",
    "notebooks/13 - Concurrency.ipynb",
    "notebooks/14 - Executors.ipynb",
    "notebooks/15 - Plugins.ipynb",
    "notebooks/16 - External Workloads.ipynb",
    "notebooks/17 - PyIngestKit Integration.ipynb",
    "notebooks/99 - Complete Workflow Lab.ipynb",
)

DX_V2_FIRST_USE_JOURNEY: tuple[str, ...] = (
    "install",
    "pwk version",
    "define task",
    "define workflow",
    "validate",
    "plan",
    "run",
    "inspect",
    "events",
    "manifest",
)

DX_V2_ADVANCED_USE_JOURNEY: tuple[str, ...] = (
    "concurrency",
    "executor capabilities",
    "plugin authoring",
    "external workload",
    "PyIngestKit integration",
    "control plane",
    "complete durable workflow",
)

DX_V2_CROSS_SURFACE_CONCEPTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "hello",
        "docs/guides/01_INSTALLATION_AND_FIRST_WORKFLOW.md",
        "examples/00_hello_world.py",
        "notebooks/01 - Hello Workflow.ipynb",
    ),
    (
        "tasks",
        "docs/guides/02_TASKS_AND_HANDLERS.md",
        "examples/01_tasks_and_handlers.py",
        "notebooks/02 - Tasks and Handlers.ipynb",
    ),
    (
        "workflow-definitions",
        "docs/guides/03_WORKFLOW_DEFINITIONS.md",
        "examples/02_workflow_definitions.py",
        "notebooks/03 - Workflow Definitions.ipynb",
    ),
    (
        "dependencies",
        "docs/guides/04_DEPENDENCIES_AND_DAG.md",
        "examples/03_dependencies.py",
        "notebooks/04 - Dependencies and DAG.ipynb",
    ),
    (
        "execution-planning",
        "docs/guides/05_EXECUTION_PLANNING.md",
        "examples/05_execution_plan.py",
        "notebooks/05 - Execution Planning.ipynb",
    ),
    (
        "runtime",
        "docs/guides/06_WORKFLOW_RUNTIME.md",
        "examples/06_runtime.py",
        "notebooks/06 - Workflow Runtime.ipynb",
    ),
    (
        "run-context",
        "docs/guides/07_RUN_CONTEXT_AND_DATA_FLOW.md",
        "examples/07_run_context.py",
        "notebooks/07 - RunContext and Data Flow.ipynb",
    ),
    (
        "retries",
        "docs/guides/08_FAILURES_AND_RETRIES.md",
        "examples/09_retry.py",
        "notebooks/08 - Failures and Retries.ipynb",
    ),
    (
        "events",
        "docs/guides/09_EVENTS_AND_OBSERVABILITY.md",
        "examples/10_events.py",
        "notebooks/09 - Events and Evidence.ipynb",
    ),
    (
        "manifest",
        "docs/guides/10_MANIFEST_AND_EVIDENCE.md",
        "examples/11_manifest.py",
        "notebooks/10 - Run Manifest.ipynb",
    ),
    (
        "sqlite",
        "docs/guides/12_SQLITE_PERSISTENCE.md",
        "examples/12_sqlite.py",
        "notebooks/11 - SQLite Persistence.ipynb",
    ),
    (
        "configuration",
        "docs/guides/14_CONFIGURATION.md",
        "examples/14_configuration.py",
        "notebooks/12 - Configuration.ipynb",
    ),
    (
        "concurrency",
        "docs/guides/16_CONCURRENCY.md",
        "examples/15_concurrency.py",
        "notebooks/13 - Concurrency.ipynb",
    ),
    (
        "executors",
        "docs/guides/18_EXECUTORS.md",
        "examples/20_custom_executor.py",
        "notebooks/14 - Executors.ipynb",
    ),
    (
        "plugins",
        "docs/guides/19_PLUGINS_AND_ECOSYSTEM.md",
        "examples/19_plugin.py",
        "notebooks/15 - Plugins.ipynb",
    ),
    (
        "external-workloads",
        "docs/guides/20_EXTERNAL_WORKLOADS.md",
        "examples/18_external_workload.py",
        "notebooks/16 - External Workloads.ipynb",
    ),
    (
        "pyingestkit",
        "docs/guides/24_PYINGESTKIT_INTEGRATION.md",
        "examples/integrations/pyingestkit/atomic_job.py",
        "notebooks/17 - PyIngestKit Integration.ipynb",
    ),
    (
        "complete-workflow",
        "docs/guides/99_COMPLETE_REFERENCE_APPLICATION.md",
        "examples/complete/data_pipeline.py",
        "notebooks/99 - Complete Workflow Lab.ipynb",
    ),
)


def developer_experience_contract_snapshot_v2() -> dict[str, object]:
    """Return the deterministic PyWorkflowKit 1.1 cross-surface DX contract."""

    return {
        "contract_version": DX_V2_CONTRACT_VERSION,
        "target_release": DX_V2_TARGET_RELEASE,
        "required_surfaces": list(DX_V2_REQUIRED_SURFACES),
        "public_authoring_facades": list(DX_V2_PUBLIC_AUTHORING_FACADES),
        "cli_commands": list(DX_V2_CLI_COMMANDS),
        "guides": list(DX_V2_CANONICAL_GUIDES),
        "examples": list(DX_V2_CANONICAL_EXAMPLES),
        "notebooks": list(DX_V2_CANONICAL_NOTEBOOKS),
        "first_use_journey": list(DX_V2_FIRST_USE_JOURNEY),
        "advanced_use_journey": list(DX_V2_ADVANCED_USE_JOURNEY),
        "cross_surface_concepts": [
            {
                "concept": concept,
                "guide": guide,
                "example": example,
                "notebook": notebook,
            }
            for concept, guide, example, notebook in DX_V2_CROSS_SURFACE_CONCEPTS
        ],
    }


__all__ = [
    "CLI_FIRST_RUN_COMMANDS",
    "DX_CONTRACT_VERSION",
    "DX_TARGET_RELEASE",
    "DX_V2_ADVANCED_USE_JOURNEY",
    "DX_V2_CANONICAL_EXAMPLES",
    "DX_V2_CANONICAL_GUIDES",
    "DX_V2_CANONICAL_NOTEBOOKS",
    "DX_V2_CLI_COMMANDS",
    "DX_V2_CONTRACT_VERSION",
    "DX_V2_CROSS_SURFACE_CONCEPTS",
    "DX_V2_FIRST_USE_JOURNEY",
    "DX_V2_PUBLIC_AUTHORING_FACADES",
    "DX_V2_REQUIRED_SURFACES",
    "DX_V2_TARGET_RELEASE",
    "EXECUTABLE_EXAMPLES",
    "GETTING_STARTED_GUIDES",
    "PUBLIC_AUTHORING_FACADES",
    "developer_experience_contract_snapshot",
    "developer_experience_contract_snapshot_v2",
]
