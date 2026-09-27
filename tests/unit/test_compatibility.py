"""Unit tests for M42 compatibility deprecation mechanics."""

from __future__ import annotations

import inspect
import warnings

import pytest

from pyworkflowkit.compatibility import (
    DeprecationEmitter,
    DeprecationKind,
    DeprecationSpec,
    PyWorkflowKitAPIDeprecationWarning,
    PyWorkflowKitCLIDeprecationWarning,
    PyWorkflowKitConfigurationDeprecationWarning,
    PyWorkflowKitPersistenceDeprecationWarning,
    PyWorkflowKitPluginDeprecationWarning,
    deprecated,
    validate_deprecation_catalog,
)


def api_spec(**overrides: object) -> DeprecationSpec:
    values: dict[str, object] = {
        "subject": "pyworkflowkit.old_api",
        "kind": DeprecationKind.API,
        "since": "0.7.0a2",
        "removal": "0.8.0",
        "replacement": "pyworkflowkit.new_api",
        "reason": "The replacement has a stable contract",
    }
    values.update(overrides)
    return DeprecationSpec(**values)  # type: ignore[arg-type]


def test_deprecation_spec_renders_versioned_replacement_guidance() -> None:
    spec = api_spec()
    assert spec.message == (
        "pyworkflowkit.old_api is deprecated since 0.7.0a2 and is planned for removal "
        "in 0.8.0. Use pyworkflowkit.new_api instead. "
        "The replacement has a stable contract."
    )


@pytest.mark.parametrize(
    ("kind", "warning_type"),
    [
        (DeprecationKind.API, PyWorkflowKitAPIDeprecationWarning),
        (DeprecationKind.CLI, PyWorkflowKitCLIDeprecationWarning),
        (DeprecationKind.CONFIGURATION, PyWorkflowKitConfigurationDeprecationWarning),
        (DeprecationKind.PLUGIN, PyWorkflowKitPluginDeprecationWarning),
        (DeprecationKind.PERSISTENCE, PyWorkflowKitPersistenceDeprecationWarning),
    ],
)
def test_warning_category_matches_contract_kind(
    kind: DeprecationKind,
    warning_type: type[Warning],
) -> None:
    assert api_spec(kind=kind).warning_type is warning_type


def test_normal_deprecation_cannot_remove_inside_same_minor_line() -> None:
    with pytest.raises(ValueError, match="next minor release line"):
        api_spec(removal="0.7.9")


def test_emergency_exception_requires_reason_and_can_use_same_line() -> None:
    with pytest.raises(ValueError, match="concrete reason"):
        api_spec(removal="0.7.9", emergency=True, reason=None)

    spec = api_spec(
        removal="0.7.9",
        emergency=True,
        reason="Security invariant requires early removal",
    )
    assert spec.emergency is True
    assert "emergency compatibility exception" in spec.message


def test_emitter_warns_once_per_deprecation_identity_and_points_to_caller() -> None:
    emitter = DeprecationEmitter()
    spec = api_spec()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        caller_line = inspect.currentframe().f_lineno + 1
        assert emitter.warn(spec) is True
        assert emitter.warn(spec) is False

    assert len(caught) == 1
    assert caught[0].filename == __file__
    assert caught[0].lineno == caller_line
    assert isinstance(caught[0].message, PyWorkflowKitAPIDeprecationWarning)
    assert caught[0].message.spec == spec


def test_deprecated_decorator_preserves_callable_and_warns_once() -> None:
    emitter = DeprecationEmitter()
    spec = api_spec(subject="legacy")

    @deprecated(spec, emitter=emitter)
    def legacy(value: int) -> int:
        """Legacy sample."""
        return value * 2

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert legacy(2) == 4
        assert legacy(3) == 6

    assert len(caught) == 1
    assert legacy.__name__ == "legacy"
    assert legacy.__doc__ == "Legacy sample."


def test_catalog_rejects_duplicate_kind_and_subject() -> None:
    first = api_spec()
    duplicate = api_spec(since="0.7.1", removal="0.8.1")
    with pytest.raises(ValueError, match="duplicate active deprecation"):
        validate_deprecation_catalog((first, duplicate))
