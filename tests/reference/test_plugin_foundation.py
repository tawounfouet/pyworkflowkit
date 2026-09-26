"""M22 plugin foundation acceptance coverage."""

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginCatalog,
    PluginDescriptor,
    PluginType,
)


def test_manual_executor_plugin_registration_is_explicit_and_lazy() -> None:
    created = 0

    def factory() -> LocalExecutor:
        nonlocal created
        created += 1
        return LocalExecutor()

    catalog = PluginCatalog()
    descriptor = PluginDescriptor(
        name="custom-local",
        plugin_type=PluginType.EXECUTOR,
        api_version=PLUGIN_API_VERSION,
        plugin_version="0.1.0",
    )

    catalog.executors.register(descriptor, factory)

    assert created == 0
    assert catalog.executors.descriptors() == (descriptor,)

    executor = catalog.executors.create("custom-local")

    assert created == 1
    assert executor.key == "local"


def test_m22_does_not_perform_automatic_discovery() -> None:
    catalog = PluginCatalog()

    assert catalog.descriptors() == ()
