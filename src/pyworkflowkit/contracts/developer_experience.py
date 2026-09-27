"""Machine-readable developer-experience contract for the PyWorkflowKit 1.0 line."""

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


__all__ = [
    "CLI_FIRST_RUN_COMMANDS",
    "DX_CONTRACT_VERSION",
    "DX_TARGET_RELEASE",
    "EXECUTABLE_EXAMPLES",
    "GETTING_STARTED_GUIDES",
    "PUBLIC_AUTHORING_FACADES",
    "developer_experience_contract_snapshot",
]
