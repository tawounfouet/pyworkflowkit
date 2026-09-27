# Plugin Ecosystem Compatibility Contract

Status: M44 — 0.7.0a4

## Purpose

M44 makes the plugin compatibility rules reusable outside the PyWorkflowKit repository.

Before M44, the runtime already checked entry-point name, plugin type, and
`PLUGIN_API_VERSION`, but that logic lived privately inside `PluginDiscovery`.

M44 extracts the same rules into a public contract suite used by both:

~~~text
PyWorkflowKit PluginDiscovery
and
third-party plugin test suites
~~~

The runtime and external authors therefore validate against the same implementation.

## Plugin API version

~~~text
PLUGIN_API_VERSION = "1"
~~~

Compatibility is exact in API v1. A plugin declaring another API version is incompatible.

## Frozen plugin categories

~~~text
executor
metadata
workload
event
~~~

No category is added by M44.

## Frozen entry-point groups

~~~text
executor  -> pyworkflowkit.executors
metadata  -> pyworkflowkit.metadata
workload  -> pyworkflowkit.workloads
event     -> pyworkflowkit.events
~~~

These mappings are exposed by `ENTRY_POINT_GROUPS` and the reverse
`PLUGIN_TYPE_BY_ENTRY_POINT_GROUP`.

## Registration contract

An entry-point provider resolves to either:

~~~text
RegisteredPlugin
or
zero-argument provider -> RegisteredPlugin
~~~

The public conformance helper validates a registration without instantiating its factory:

~~~python
from pyworkflowkit.plugins import (
    ENTRY_POINT_GROUPS,
    PluginType,
    validate_plugin_registration,
)

report = validate_plugin_registration(
    registration,
    entry_point_name="acme",
    entry_point_group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
)

assert report.compatible, report.summary()
~~~

The metadata contract checks:

~~~text
entry-point group is known
provider result is RegisteredPlugin
descriptor.name == entry-point name
descriptor.plugin_type == group type
descriptor.api_version == PLUGIN_API_VERSION
factory is callable
~~~

## Assertion helper

A third-party test may prefer fail-fast behavior:

~~~python
from pyworkflowkit.plugins import assert_plugin_registration_compatible

assert_plugin_registration_compatible(
    registration,
    entry_point_name="acme",
    entry_point_group="pyworkflowkit.executors",
)
~~~

Incompatibility raises the existing public `PluginCompatibilityError`.

## Instance conformance

Registration validation does not call the factory.

This is intentional because plugin construction may allocate threads, open files,
connect to databases, or perform other side effects.

A plugin author who explicitly creates an instance can separately validate it:

~~~python
from pyworkflowkit.plugins import (
    PluginType,
    assert_plugin_instance_compatible,
)

instance = registration.create()

assert_plugin_instance_compatible(
    instance,
    plugin_type=PluginType.EXECUTOR,
)
~~~

The API-v1 structural contracts are:

~~~text
executor -> Executor
metadata -> MetadataStore
event    -> RuntimeEventSink
workload -> no additional runtime Protocol in API v1
~~~

The workload category remains intentionally generic. M44 does not invent a workload
protocol merely for symmetry.

## Example third-party packaging

~~~toml
[project.entry-points."pyworkflowkit.executors"]
acme = "acme_pyworkflowkit:plugin"
~~~

~~~python
from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
)


def plugin() -> RegisteredPlugin[LocalExecutor]:
    return RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="acme",
            plugin_type=PluginType.EXECUTOR,
            api_version=PLUGIN_API_VERSION,
            plugin_version="1.2.0",
        ),
        factory=LocalExecutor,
    )
~~~

A plugin repository can then run:

~~~python
def test_pyworkflowkit_contract() -> None:
    registration = plugin()

    assert_plugin_registration_compatible(
        registration,
        entry_point_name="acme",
        entry_point_group="pyworkflowkit.executors",
    )

    assert_plugin_instance_compatible(
        registration.create(),
        plugin_type=PluginType.EXECUTOR,
    )
~~~

No importlib metadata installation is required for this direct contract test.

## Diagnostic codes

Reports use stable machine-readable issue codes:

~~~text
registration_type
entry_point_group
descriptor_name
descriptor_type
api_version
factory
instance_type
~~~

Human-readable messages remain diagnostic text and should not be parsed as a machine
protocol.

## Discovery integration

`PluginDiscovery` now delegates compatibility validation to the public contract suite.

The discovery lifecycle remains unchanged:

~~~text
discover metadata
    ↓
do not import plugin
    ↓
explicit enablement
    ↓
load provider
    ↓
validate public plugin contract
    ↓
register compatible plugin
~~~

M44 does not make discovery automatic.

## Compatibility policy

Within Plugin API v1, changing any of the following is a stable-intent change:

~~~text
PluginType values
entry-point groups
PluginDescriptor field meaning
RegisteredPlugin provider shape
exact Plugin API compatibility rule
public issue-code meaning
Executor / MetadataStore / RuntimeEventSink structural requirement
~~~

Such a change requires M42 deprecation where applicable or a Plugin API version
transition.

## Scope boundary

M44 does not add:

~~~text
automatic plugin enablement
remote plugin registry
package marketplace
dependency solver
plugin sandbox
dynamic installation
new workload domain model
new plugin category
~~~

## Next

M45 — Persistence and Migration Compatibility.
