"""M42 reference acceptance for controlled deprecation semantics."""

from pyworkflowkit.compatibility import (
    ACTIVE_DEPRECATIONS,
    MINIMUM_DEPRECATION_MINOR_LINES,
    DeprecationKind,
    DeprecationSpec,
    PyWorkflowKitAPIDeprecationWarning,
    PyWorkflowKitCLIDeprecationWarning,
    PyWorkflowKitConfigurationDeprecationWarning,
    PyWorkflowKitDeprecationWarning,
    PyWorkflowKitPersistenceDeprecationWarning,
    PyWorkflowKitPluginDeprecationWarning,
)


def test_m42_deprecation_categories_are_frozen() -> None:
    assert tuple(item.value for item in DeprecationKind) == (
        "api",
        "cli",
        "configuration",
        "plugin",
        "persistence",
    )


def test_m42_warnings_are_visible_future_warnings() -> None:
    assert issubclass(PyWorkflowKitDeprecationWarning, FutureWarning)
    assert issubclass(PyWorkflowKitAPIDeprecationWarning, PyWorkflowKitDeprecationWarning)
    assert issubclass(PyWorkflowKitCLIDeprecationWarning, PyWorkflowKitDeprecationWarning)
    assert issubclass(
        PyWorkflowKitConfigurationDeprecationWarning,
        PyWorkflowKitDeprecationWarning,
    )
    assert issubclass(PyWorkflowKitPluginDeprecationWarning, PyWorkflowKitDeprecationWarning)
    assert issubclass(
        PyWorkflowKitPersistenceDeprecationWarning,
        PyWorkflowKitDeprecationWarning,
    )


def test_m42_default_window_requires_next_minor_release_line() -> None:
    assert MINIMUM_DEPRECATION_MINOR_LINES == 1
    spec = DeprecationSpec(
        subject="sample",
        kind=DeprecationKind.API,
        since="0.7.0a2",
        removal="0.8.0",
        replacement="replacement",
    )
    assert spec.since == "0.7.0a2"
    assert spec.removal == "0.8.0"


def test_m42_introduces_mechanism_without_deprecating_existing_contracts() -> None:
    assert ACTIVE_DEPRECATIONS == ()
