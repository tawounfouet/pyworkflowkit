"""Compatibility and deprecation contracts for PyWorkflowKit."""

from __future__ import annotations

import re
import warnings
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import wraps
from types import MappingProxyType
from typing import ParamSpec, TypeVar

MINIMUM_DEPRECATION_MINOR_LINES = 1
COMPATIBILITY_CONTRACT_VERSION = "1"
COMPATIBILITY_TARGET_RELEASE = "1.0.0"
_VERSION_LINE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.|$)")


class CompatibilityStatus(StrEnum):
    STABLE = "stable"
    DEPRECATED = "deprecated"
    INTERNAL = "internal"
    REMOVE_BEFORE_1_0 = "remove-before-1.0"


@dataclass(frozen=True, slots=True)
class CompatibilitySubject:
    key: str
    area: str
    status: CompatibilityStatus
    contract_version: str | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("compatibility subject key must be a non-empty string")
        if not isinstance(self.area, str) or not self.area.strip():
            raise ValueError("compatibility subject area must be a non-empty string")
        if not isinstance(self.status, CompatibilityStatus):
            raise TypeError("compatibility subject status must be a CompatibilityStatus")
        if self.contract_version is not None and not self.contract_version.strip():
            raise ValueError("compatibility contract_version must not be blank")
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("compatibility rationale must not be blank")


CONSOLE_SCRIPT_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "pyworkflow": "pyworkflowkit.cli:main",
        "pyworkflowkit": "pyworkflowkit.cli:main",
    }
)

CONFIGURATION_PRECEDENCE: tuple[str, ...] = (
    "explicit_overrides",
    "toml",
    "environment",
    "defaults",
)

RUNTIME_CONFIGURATION_DEFAULTS: Mapping[str, object] = MappingProxyType(
    {
        "runtime.workspace": ".pyworkflow",
        "metadata.backend": "memory",
        "metadata.sqlite_path": "state/pyworkflow.sqlite3",
        "metadata.sqlite_busy_timeout_ms": 5_000,
        "metadata.sqlite_wal": True,
        "metadata.postgres_dsn": None,
        "metadata.postgres_pool_size": 5,
        "metadata.postgres_max_overflow": 10,
        "metadata.postgres_application_name": "pyworkflowkit",
    }
)

STABLE_EXCEPTION_EXPORTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "pyworkflowkit": ("PyWorkflowKitError",),
        "pyworkflowkit.control_plane": (
            "ControlPlaneCapabilityError",
            "ControlPlaneProviderError",
        ),
    }
)

INTERNAL_MODULE_PREFIXES: tuple[str, ...] = (
    "pyworkflowkit.adapters",
    "pyworkflowkit.application",
    "pyworkflowkit.cli",
    "pyworkflowkit.cli_contract",
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


class DeprecationKind(StrEnum):
    API = "api"
    CLI = "cli"
    CONFIGURATION = "configuration"
    PLUGIN = "plugin"
    PERSISTENCE = "persistence"


class PyWorkflowKitDeprecationWarning(FutureWarning):
    def __init__(self, spec: DeprecationSpec) -> None:
        self.spec = spec
        super().__init__(spec.message)


class PyWorkflowKitAPIDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


class PyWorkflowKitCLIDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


class PyWorkflowKitConfigurationDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


class PyWorkflowKitPluginDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


class PyWorkflowKitPersistenceDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


_WARNING_TYPES: dict[DeprecationKind, type[PyWorkflowKitDeprecationWarning]] = {
    DeprecationKind.API: PyWorkflowKitAPIDeprecationWarning,
    DeprecationKind.CLI: PyWorkflowKitCLIDeprecationWarning,
    DeprecationKind.CONFIGURATION: PyWorkflowKitConfigurationDeprecationWarning,
    DeprecationKind.PLUGIN: PyWorkflowKitPluginDeprecationWarning,
    DeprecationKind.PERSISTENCE: PyWorkflowKitPersistenceDeprecationWarning,
}


@dataclass(frozen=True, slots=True)
class DeprecationSpec:
    subject: str
    kind: DeprecationKind
    since: str
    removal: str
    replacement: str | None = None
    reason: str | None = None
    emergency: bool = False

    def __post_init__(self) -> None:
        _require_text(self.subject, field_name="subject")
        if not isinstance(self.kind, DeprecationKind):
            raise TypeError("kind must be a DeprecationKind")
        _require_text(self.since, field_name="since")
        _require_text(self.removal, field_name="removal")
        if self.replacement is not None:
            _require_text(self.replacement, field_name="replacement")
        if self.reason is not None:
            _require_text(self.reason, field_name="reason")
        if self.emergency and self.reason is None:
            raise ValueError("emergency deprecation requires a concrete reason")

        if not self.emergency and not _is_later_release_line(
            since=_release_line(self.since),
            removal=_release_line(self.removal),
        ):
            raise ValueError(
                "normal deprecation removal must target at least the next minor release line"
            )

    @property
    def message(self) -> str:
        parts = [
            (
                f"{self.subject} is deprecated since {self.since} and is planned "
                f"for removal in {self.removal}."
            )
        ]
        if self.replacement is not None:
            parts.append(f"Use {self.replacement} instead.")
        if self.reason is not None:
            parts.append(f"{self.reason.rstrip('.')}.")
        if self.emergency:
            parts.append("This deprecation uses the documented emergency compatibility exception.")
        return " ".join(parts)

    @property
    def warning_type(self) -> type[PyWorkflowKitDeprecationWarning]:
        return _WARNING_TYPES[self.kind]

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (self.kind.value, self.subject, self.since, self.removal)


class DeprecationEmitter:
    def __init__(self) -> None:
        self._emitted: set[tuple[str, str, str, str]] = set()

    def warn(self, spec: DeprecationSpec, *, stacklevel: int = 2) -> bool:
        if stacklevel < 1:
            raise ValueError("stacklevel must be greater than or equal to 1")
        if spec.identity in self._emitted:
            return False
        warnings.warn(spec.warning_type(spec), stacklevel=stacklevel)
        self._emitted.add(spec.identity)
        return True

    @property
    def emitted_identities(self) -> frozenset[tuple[str, str, str, str]]:
        return frozenset(self._emitted)


_DEFAULT_EMITTER = DeprecationEmitter()


def warn_deprecated(spec: DeprecationSpec, *, stacklevel: int = 2) -> bool:
    return _DEFAULT_EMITTER.warn(spec, stacklevel=stacklevel + 1)


P = ParamSpec("P")
R = TypeVar("R")


def deprecated(
    spec: DeprecationSpec,
    *,
    emitter: DeprecationEmitter | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    selected_emitter = emitter if emitter is not None else _DEFAULT_EMITTER

    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            selected_emitter.warn(spec, stacklevel=3)
            return function(*args, **kwargs)

        return wrapper

    return decorator


def validate_deprecation_catalog(specs: Iterable[DeprecationSpec]) -> tuple[DeprecationSpec, ...]:
    values = tuple(specs)
    seen: set[tuple[DeprecationKind, str]] = set()
    for spec in values:
        key = (spec.kind, spec.subject)
        if key in seen:
            raise ValueError(f"duplicate active deprecation for {spec.kind.value}:{spec.subject}")
        seen.add(key)
    return tuple(sorted(values, key=lambda spec: (spec.kind.value, spec.subject)))


ACTIVE_DEPRECATIONS: tuple[DeprecationSpec, ...] = validate_deprecation_catalog(())


def _validate_compatibility_subjects(
    subjects: Iterable[CompatibilitySubject],
) -> tuple[CompatibilitySubject, ...]:
    values = tuple(subjects)
    seen: set[str] = set()
    for subject in values:
        if subject.key in seen:
            raise ValueError(f"duplicate compatibility subject: {subject.key}")
        seen.add(subject.key)
    return tuple(sorted(values, key=lambda subject: subject.key))


COMPATIBILITY_SUBJECTS: tuple[CompatibilitySubject, ...] = _validate_compatibility_subjects(
    (
        CompatibilitySubject(
            key="api.frozen_facades",
            area="api",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="RQ-01 public facades are the intended 1.0 import surfaces.",
        ),
        CompatibilitySubject(
            key="cli.machine_contract",
            area="cli",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Commands, JSON keys, and exit codes are machine-facing contracts.",
        ),
        CompatibilitySubject(
            key="cli.console_script.pyworkflow",
            area="cli",
            status=CompatibilityStatus.STABLE,
            rationale="Canonical console entry point.",
        ),
        CompatibilitySubject(
            key="cli.console_script.pyworkflowkit",
            area="cli",
            status=CompatibilityStatus.STABLE,
            rationale="Documented console alias retained through 1.0.",
        ),
        CompatibilitySubject(
            key="configuration.runtime_settings",
            area="configuration",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="RuntimeSettings precedence and defaults are frozen for 1.0.",
        ),
        CompatibilitySubject(
            key="exceptions.facade_exports",
            area="exceptions",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Only exception types re-exported through frozen facades are 1.0-stable.",
        ),
        CompatibilitySubject(
            key="schema.manifest",
            area="schema",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="RunManifest remains the portable execution evidence schema.",
        ),
        CompatibilitySubject(
            key="typing.static_contract",
            area="typing",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Frozen facades are qualified as PEP 561 typed strict-consumer surfaces.",
        ),
        CompatibilitySubject(
            key="plugin.api",
            area="plugin",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Plugin registration and discovery compatibility remains Plugin API v1.",
        ),
        CompatibilitySubject(
            key="persistence.schema",
            area="persistence",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Metadata persistence schema contract remains v1.",
        ),
        CompatibilitySubject(
            key="persistence.migrations",
            area="persistence",
            status=CompatibilityStatus.STABLE,
            contract_version="0003_retry_eligible_at",
            rationale="Published migration revisions remain immutable and upgradeable.",
        ),
        CompatibilitySubject(
            key="control_plane.provider",
            area="integration",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Control-plane provider operations and schemas remain contract v1.",
        ),
        CompatibilitySubject(
            key="ecosystem.sdk",
            area="integration",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="The v1 ecosystem SDK remains compatible across the 0.8 and 0.9 lines.",
        ),
        CompatibilitySubject(
            key="integration.external_workload",
            area="integration",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Atomic external-workload interoperability remains contract v1.",
        ),
        CompatibilitySubject(
            key="integration.references",
            area="integration",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Portable artifact and external-run references remain contract v1.",
        ),
        CompatibilitySubject(
            key="integration.observability",
            area="integration",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Observability projection remains interoperability contract v1.",
        ),
        CompatibilitySubject(
            key="deprecation.policy",
            area="deprecation",
            status=CompatibilityStatus.STABLE,
            contract_version="1",
            rationale="Normal removals require an explicit deprecation window.",
        ),
        CompatibilitySubject(
            key="module.adapters",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Concrete adapters are implementation details unless re-exported.",
        ),
        CompatibilitySubject(
            key="module.application",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Application services are not direct 1.0 import contracts.",
        ),
        CompatibilitySubject(
            key="module.cli",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="The Python CLI implementation module is not a direct public API.",
        ),
        CompatibilitySubject(
            key="module.cli_contract",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="CLI contract semantics are stable; the implementation module path is not.",
        ),
        CompatibilitySubject(
            key="module.compatibility",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Compatibility metadata is release tooling rather than a frozen user facade.",
        ),
        CompatibilitySubject(
            key="module.config",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="RuntimeSettings is stable via the facade; config internals are not.",
        ),
        CompatibilitySubject(
            key="module.contracts",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Reference/serialization implementation paths are not public facades.",
        ),
        CompatibilitySubject(
            key="module.declarative",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Declarative helpers are stable through package-root re-exports.",
        ),
        CompatibilitySubject(
            key="module.domain",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Domain module paths may evolve; facade re-exports remain stable.",
        ),
        CompatibilitySubject(
            key="module.errors",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Stable exception types are those re-exported through frozen facades.",
        ),
        CompatibilitySubject(
            key="module.migrations",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Migration identifiers are stable, migration implementation paths are not.",
        ),
        CompatibilitySubject(
            key="module.ports",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Port module paths are internal; facade-provided protocols remain stable.",
        ),
        CompatibilitySubject(
            key="module.release_contract",
            area="module",
            status=CompatibilityStatus.INTERNAL,
            rationale="Release qualification metadata is not a frozen runtime import facade.",
        ),
    )
)


def compatibility_contract_snapshot() -> dict[str, object]:
    """Return the deterministic RQ-02 compatibility and deprecation classification."""

    by_status = {
        status.value: [
            subject.key for subject in COMPATIBILITY_SUBJECTS if subject.status is status
        ]
        for status in CompatibilityStatus
    }
    return {
        "contract_version": COMPATIBILITY_CONTRACT_VERSION,
        "target_release": COMPATIBILITY_TARGET_RELEASE,
        "subjects": [
            {
                "key": subject.key,
                "area": subject.area,
                "status": subject.status.value,
                "contract_version": subject.contract_version,
                "rationale": subject.rationale,
            }
            for subject in COMPATIBILITY_SUBJECTS
        ],
        "by_status": by_status,
        "console_scripts": dict(sorted(CONSOLE_SCRIPT_ALIASES.items())),
        "configuration": {
            "precedence": list(CONFIGURATION_PRECEDENCE),
            "defaults": dict(sorted(RUNTIME_CONFIGURATION_DEFAULTS.items())),
        },
        "stable_exception_exports": {
            module_name: list(names)
            for module_name, names in sorted(STABLE_EXCEPTION_EXPORTS.items())
        },
        "internal_module_prefixes": list(INTERNAL_MODULE_PREFIXES),
        "active_deprecations": [
            {
                "subject": spec.subject,
                "kind": spec.kind.value,
                "since": spec.since,
                "removal": spec.removal,
                "replacement": spec.replacement,
                "reason": spec.reason,
                "emergency": spec.emergency,
            }
            for spec in ACTIVE_DEPRECATIONS
        ],
    }


def _require_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _release_line(value: str) -> tuple[int, int]:
    match = _VERSION_LINE.match(value)
    if match is None:
        raise ValueError(f"version '{value}' must start with a numeric major.minor release line")
    return (int(match.group("major")), int(match.group("minor")))


def _is_later_release_line(
    *,
    since: tuple[int, int],
    removal: tuple[int, int],
) -> bool:
    since_major, since_minor = since
    removal_major, removal_minor = removal
    if removal_major > since_major:
        return True
    if removal_major < since_major:
        return False
    return removal_minor >= since_minor + MINIMUM_DEPRECATION_MINOR_LINES


__all__ = [
    "ACTIVE_DEPRECATIONS",
    "COMPATIBILITY_CONTRACT_VERSION",
    "COMPATIBILITY_SUBJECTS",
    "COMPATIBILITY_TARGET_RELEASE",
    "CONFIGURATION_PRECEDENCE",
    "CONSOLE_SCRIPT_ALIASES",
    "INTERNAL_MODULE_PREFIXES",
    "MINIMUM_DEPRECATION_MINOR_LINES",
    "RUNTIME_CONFIGURATION_DEFAULTS",
    "STABLE_EXCEPTION_EXPORTS",
    "CompatibilityStatus",
    "CompatibilitySubject",
    "DeprecationEmitter",
    "DeprecationKind",
    "DeprecationSpec",
    "PyWorkflowKitAPIDeprecationWarning",
    "PyWorkflowKitCLIDeprecationWarning",
    "PyWorkflowKitConfigurationDeprecationWarning",
    "PyWorkflowKitDeprecationWarning",
    "PyWorkflowKitPersistenceDeprecationWarning",
    "PyWorkflowKitPluginDeprecationWarning",
    "deprecated",
    "validate_deprecation_catalog",
    "compatibility_contract_snapshot",
    "warn_deprecated",
]
