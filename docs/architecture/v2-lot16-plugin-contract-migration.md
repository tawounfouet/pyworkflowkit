# PyWorkflowKit V2 — LOT-16 Plugin Contract Migration

## Status

LOT-16 migrates the plugin extension boundary to the canonical V2 runtime contracts
without changing the frozen PyWorkflowKit 1.1 plugin API.

The V2 surface is intentionally additive:

```text
pyworkflowkit.plugins
    = frozen 1.1 plugin API

pyworkflowkit.plugins.v2
    = canonical V2 plugin migration contract
```

## Why a separate V2 plugin API is required

Before LOT-16, the plugin system validated instances against the historical 1.1 ports:

```text
pyworkflowkit.ports.executor.Executor
pyworkflowkit.ports.metadata_store.MetadataStore
pyworkflowkit.ports.observability.RuntimeEventSink
```

The canonical V2 runtime now owns different contracts:

```text
pyworkflowkit.executors.Executor
pyworkflowkit.persistence.MetadataStore
pyworkflowkit.runtime.RuntimeEvent
```

Rebinding the existing 1.1 plugin names in place would silently change the meaning of a
published extension contract.

LOT-16 therefore introduces a new explicit plugin API version.

## Plugin API version

```text
V2_PLUGIN_API_VERSION = "2"
V2_PLUGIN_CONTRACT_VERSION = "1"
```

The API version identifies extension compatibility.

The contract version identifies this machine-readable LOT-16 contract snapshot.

## Entry-point isolation

V1 entry-point groups remain unchanged:

```text
pyworkflowkit.executors
pyworkflowkit.metadata
pyworkflowkit.workloads
pyworkflowkit.events
```

V2 uses disjoint groups:

```text
pyworkflowkit.v2.executors
pyworkflowkit.v2.metadata
pyworkflowkit.v2.workloads
pyworkflowkit.v2.events
```

This prevents an installed V1 plugin from being interpreted as a V2 plugin merely
because it has the same logical category.

There is no automatic V1 -> V2 bridge.

## V2 plugin categories

### Executor

A V2 executor plugin instance must satisfy:

```text
pyworkflowkit.executors.Executor
```

This means the V2 descriptor/request/result execution contract, not the historical
`key + capabilities + execute(task, handler, context)` port.

### Metadata

A V2 metadata plugin instance must satisfy:

```text
pyworkflowkit.persistence.MetadataStore
```

This includes the canonical V2 runtime-state, attempts, transition evidence,
RuntimeEvent projection, output checkpoints and manifest-reference hooks.

### Workload

LOT-16 introduces:

```python
V2WorkloadBinding(
    registry_key="jobs.refresh",
    handler=refresh_job,
)
```

The binding makes the extension boundary explicit:

```text
RegisteredWorkload.registry_key
        ↓
V2WorkloadBinding.registry_key
        ↓
callable handler
```

A workload plugin is therefore not an arbitrary object with framework-specific magic
methods.

### Event

A V2 event plugin must satisfy:

```text
V2RuntimeEventSink
    name: str
    emit(event: pyworkflowkit.runtime.RuntimeEvent) -> None
```

The V2 event type is the semantic evidence introduced in LOT-12.

## Registration contract

A V2 entry point must resolve to either:

```text
V2RegisteredPlugin
```

or a zero-argument provider returning one.

The descriptor must contain:

```text
name
plugin_type
api_version = "2"
plugin_version?
description?
```

Registration validation is metadata-only.

It must not instantiate the actual plugin.

## Discovery lifecycle

```text
installed distribution metadata
        ↓
V2PluginDiscovery.discover()
        ↓
metadata-only V2DiscoveredPlugin
        ↓
explicit enable_selected(...)
        ↓
load provider
        ↓
validate V2RegisteredPlugin
        ↓
register lazy factory
        ↓
explicit registry.create(name)
        ↓
construct instance
        ↓
validate canonical V2 instance contract
```

Importing PyWorkflowKit or discovering metadata does not activate plugin code.

## Failure posture

LOT-16 is fail-closed.

The following are rejected:

```text
V1 RegisteredPlugin presented to V2
unknown V2 entry-point group
descriptor / entry-point name mismatch
descriptor / category mismatch
api_version != "2"
non-callable factory
executor not satisfying V2 Executor
metadata store not satisfying V2 MetadataStore
workload not returning V2WorkloadBinding
event sink not satisfying V2RuntimeEventSink
duplicate registrations
missing explicitly-enabled plugin
```

## Compatibility

LOT-16 does not modify:

```text
PLUGIN_API_VERSION = "1"
PluginDescriptor
RegisteredPlugin
PluginRegistry
PluginCatalog
PluginDiscovery
ENTRY_POINT_GROUPS
```

from `pyworkflowkit.plugins`.

It also does not promote V2 plugin names to the frozen package root.

## Contract snapshot

`v2_plugin_contract_snapshot()` freezes:

```text
plugin API version
entry-point groups
four plugin categories
canonical executor contract
canonical metadata contract
workload binding contract
V2 runtime event sink contract
metadata-first discovery
explicit enablement
no implicit V1 bridge
no instance construction during registration validation
```

## Acceptance invariants

LOT-16 proves:

```text
V1 and V2 entry-point groups are disjoint
V1 registration is not implicitly V2 compatible
legacy LocalExecutor does not satisfy V2 executor plugin contract
canonical InlineExecutor does satisfy V2 executor plugin contract
canonical InMemoryMetadataStore satisfies V2 metadata plugin contract
workload plugins return explicit V2WorkloadBinding
event plugins target V2 RuntimeEvent
all registry creation paths validate instance compatibility
wrong plugin API versions fail closed
V1 plugin API remains unchanged
V2 surface is qualified under pyworkflowkit.plugins.v2
V2 names are not promoted to the frozen root
```

## Scope boundary

LOT-16 migrates extension contracts.

It does not yet:

```text
rewrite independently published V1 plugins automatically
activate plugins on import
create a distributed plugin marketplace
serialize arbitrary plugin instances
load Python types from wire payloads
change the frozen 1.1 public API
```

The next roadmap lot should consume the V2 plugin boundary from the remaining V2
integration/runtime surfaces rather than reopening plugin compatibility semantics.
