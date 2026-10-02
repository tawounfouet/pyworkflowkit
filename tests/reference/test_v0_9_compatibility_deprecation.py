"""RQ-02 acceptance for compatibility and deprecation stabilization."""

from __future__ import annotations

import json
from importlib import import_module
from importlib.metadata import entry_points

import pytest

from pyworkflowkit.application.manifest import MANIFEST_SCHEMA_VERSION
from pyworkflowkit.cli_contract import CLI_MACHINE_CONTRACT_VERSION
from pyworkflowkit.compatibility import (
    ACTIVE_DEPRECATIONS,
    COMPATIBILITY_CONTRACT_VERSION,
    COMPATIBILITY_SUBJECTS,
    COMPATIBILITY_TARGET_RELEASE,
    CONFIGURATION_PRECEDENCE,
    CONSOLE_SCRIPT_ALIASES,
    INTERNAL_MODULE_PREFIXES,
    RUNTIME_CONFIGURATION_DEFAULTS,
    STABLE_EXCEPTION_EXPORTS,
    CompatibilityStatus,
    DeprecationKind,
    DeprecationSpec,
    compatibility_contract_snapshot,
)
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.contracts.release_candidate import RELEASE_CANDIDATE_CONTRACT_VERSION
from pyworkflowkit.control_plane import CONTROL_PLANE_PROVIDER_CONTRACT_VERSION
from pyworkflowkit.ecosystem import (
    ECOSYSTEM_COMPATIBILITY_SERIES,
    ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION,
    ECOSYSTEM_MINIMUM_VERSION,
    ECOSYSTEM_SDK_CONTRACT_VERSION,
)
from pyworkflowkit.errors import PyWorkflowKitError
from pyworkflowkit.integrations import (
    EXTERNAL_WORKLOAD_CONTRACT_VERSION,
    OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION,
    REFERENCE_INTEROPERABILITY_CONTRACT_VERSION,
)
from pyworkflowkit.migrations.contract import (
    MIGRATION_HEAD_REVISION,
    PERSISTENCE_SCHEMA_CONTRACT_VERSION,
)
from pyworkflowkit.plugins import PLUGIN_API_VERSION
from pyworkflowkit.public_api import PUBLIC_API_CONTRACT_VERSION, PUBLIC_API_SURFACES
from pyworkflowkit.release_contract import release_contract_snapshot


def test_rq02_classification_contract_targets_1_0() -> None:
    assert COMPATIBILITY_CONTRACT_VERSION == "1"
    assert COMPATIBILITY_TARGET_RELEASE == "1.0.0"
    assert tuple(status.value for status in CompatibilityStatus) == (
        "stable",
        "deprecated",
        "internal",
        "remove-before-1.0",
    )

    keys = tuple(subject.key for subject in COMPATIBILITY_SUBJECTS)
    assert len(keys) == len(set(keys))


def test_rq02_all_versioned_contracts_remain_v1() -> None:
    assert PUBLIC_API_CONTRACT_VERSION == "1"
    assert CLI_MACHINE_CONTRACT_VERSION == "1"
    assert MANIFEST_SCHEMA_VERSION == "1"
    assert PLUGIN_API_VERSION == "1"
    assert PERSISTENCE_SCHEMA_CONTRACT_VERSION == "1"
    assert CONTROL_PLANE_PROVIDER_CONTRACT_VERSION == "1"
    assert ECOSYSTEM_SDK_CONTRACT_VERSION == "1"
    assert EXTERNAL_WORKLOAD_CONTRACT_VERSION == "1"
    assert REFERENCE_INTEROPERABILITY_CONTRACT_VERSION == "1"
    assert OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION == "1"
    assert RELEASE_CANDIDATE_CONTRACT_VERSION == "1"
    assert MIGRATION_HEAD_REVISION == "0004_v2_runtime_metadata"


def test_rq02_ecosystem_sdk_v1_covers_0_8_through_1_x() -> None:
    assert ECOSYSTEM_COMPATIBILITY_SERIES == "0.8-1.x"
    assert ECOSYSTEM_MINIMUM_VERSION == "0.8.0b1"
    assert ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION == "2.0"


def test_rq02_console_aliases_are_installed_and_stable() -> None:
    installed = {
        entry_point.name: entry_point.value
        for entry_point in entry_points(group="console_scripts")
        if entry_point.name in CONSOLE_SCRIPT_ALIASES
    }

    assert installed == dict(CONSOLE_SCRIPT_ALIASES)


def test_rq02_configuration_precedence_and_defaults_are_frozen() -> None:
    assert CONFIGURATION_PRECEDENCE == (
        "explicit_overrides",
        "toml",
        "environment",
        "defaults",
    )

    settings = RuntimeSettings.model_validate({})
    observed = {
        "runtime.workspace": str(settings.runtime.workspace),
        "metadata.backend": settings.metadata.backend,
        "metadata.sqlite_path": str(settings.metadata.sqlite_path),
        "metadata.sqlite_busy_timeout_ms": settings.metadata.sqlite_busy_timeout_ms,
        "metadata.sqlite_wal": settings.metadata.sqlite_wal,
        "metadata.postgres_dsn": settings.metadata.postgres_dsn,
        "metadata.postgres_pool_size": settings.metadata.postgres_pool_size,
        "metadata.postgres_max_overflow": settings.metadata.postgres_max_overflow,
        "metadata.postgres_application_name": settings.metadata.postgres_application_name,
    }

    assert observed == dict(RUNTIME_CONFIGURATION_DEFAULTS)


def test_rq02_only_facade_reexported_exceptions_are_1_0_stable() -> None:
    for module_name, exception_names in STABLE_EXCEPTION_EXPORTS.items():
        assert module_name in PUBLIC_API_SURFACES
        module = import_module(module_name)

        for exception_name in exception_names:
            assert exception_name in PUBLIC_API_SURFACES[module_name]
            exception_type = getattr(module, exception_name)
            assert issubclass(exception_type, PyWorkflowKitError)


def test_rq02_internal_module_prefixes_do_not_overlap_frozen_facades() -> None:
    assert INTERNAL_MODULE_PREFIXES == (
        "pyworkflowkit.adapters",
        "pyworkflowkit.application",
        "pyworkflowkit.cli",
        "pyworkflowkit.cli_contract",
        "pyworkflowkit.cli_rendering",
        "pyworkflowkit.compatibility",
        "pyworkflowkit.config",
        "pyworkflowkit.contracts",
        "pyworkflowkit.declarative",
        "pyworkflowkit.domain",
        "pyworkflowkit.errors",
        "pyworkflowkit.migrations",
        "pyworkflowkit.ports",
        "pyworkflowkit.release_contract",
    )

    for module_name in PUBLIC_API_SURFACES:
        assert all(
            module_name != prefix and not module_name.startswith(f"{prefix}.")
            for prefix in INTERNAL_MODULE_PREFIXES
        )


def test_rq02_has_no_active_deprecation_or_pre_1_0_removal() -> None:
    snapshot = compatibility_contract_snapshot()

    assert ACTIVE_DEPRECATIONS == ()
    assert snapshot["by_status"]["deprecated"] == []
    assert snapshot["by_status"]["remove-before-1.0"] == []

    # The policy permits a 0.9 deprecation to target the 1.0 line,
    # but rejects removal inside the same 0.9 release line.
    allowed = DeprecationSpec(
        subject="sample",
        kind=DeprecationKind.API,
        since="0.9.0a2",
        removal="1.0.0",
    )
    assert allowed.removal == "1.0.0"

    with pytest.raises(ValueError):
        DeprecationSpec(
            subject="sample",
            kind=DeprecationKind.API,
            since="0.9.0a2",
            removal="0.9.0",
        )


def test_rq02_snapshot_is_json_portable_and_part_of_release_contract() -> None:
    snapshot = compatibility_contract_snapshot()
    encoded = json.dumps(snapshot, allow_nan=False, sort_keys=True)
    assert json.loads(encoded) == snapshot

    release_snapshot = release_contract_snapshot()
    assert release_snapshot["compatibility"] == snapshot
