# Ecosystem SDK and Conformance Matrix

Status: M52 — 0.8.0b1

## Purpose

M52 turns the interoperability contracts established by M47-M51 into a usable authoring
surface for third-party packages.

The public authoring entry point is:

~~~python
from pyworkflowkit.ecosystem import ...
~~~

The SDK is a facade over existing stable/dedicated contracts. It is not a second plugin
system and does not replace the underlying runtime.

## Contract version

~~~text
ECOSYSTEM_SDK_CONTRACT_VERSION = "1"
~~~

Compatibility window:

~~~text
series            = 0.8
minimum           = 0.8.0b1
maximum_exclusive = 0.9
~~~

Supported Python matrix:

~~~text
3.11
3.12
3.13
~~~

## Consolidated author surface

The SDK exposes the author-facing contracts required for typical integrations:

~~~text
PluginDescriptor
PluginType
RegisteredPlugin
PluginDiscovery
PluginCatalog
Executor / ExecutorCapabilities
MetadataStore / UnitOfWork
RuntimeEventSink
ExternalWorkload / ExternalWorkloadResult
ExternalRunRef / ArtifactReference / TaskResult
TelemetryBackend / RuntimeTelemetrySink
ControlPlaneProvider / WorkflowRuntimeProvider
~~~

The package root remains unchanged.

## Authoring helper

Instead of manually repeating Plugin API metadata, authors may use:

~~~python
plugin_registration(
    name="my-workload",
    plugin_type=PluginType.WORKLOAD,
    factory=MyWorkload,
    plugin_version="1.0.0",
)
~~~

The helper creates PluginDescriptor, uses the current PLUGIN_API_VERSION, selects the
frozen entry-point group, validates registration compatibility, and returns
RegisteredPlugin.

It does not discover, install, or enable code automatically.

## Entry-point helper

~~~python
entry_point_group(PluginType.WORKLOAD)
~~~

returns:

~~~text
pyworkflowkit.workloads
~~~

The frozen mapping remains:

~~~text
executor -> pyworkflowkit.executors
metadata -> pyworkflowkit.metadata
workload -> pyworkflowkit.workloads
event    -> pyworkflowkit.events
~~~

## Conformance helpers

M52 adds dependency-free author checks:

~~~python
validate_plugin_conformance(...)
assert_plugin_conforms(...)
~~~

Validation combines entry-point name/group compatibility, descriptor type, Plugin API
version, factory contract, created-instance structural contract, and the ExternalWorkload
protocol for workload plugins.

The validate variant returns a report and does not raise for ordinary incompatibility.
The assert variant raises the existing public PluginCompatibilityError.

No pytest dependency is required.

## Machine-readable compatibility snapshot

~~~python
ecosystem_contract_snapshot()
~~~

returns deterministic JSON-compatible metadata:

~~~text
package_version
sdk_contract_version
compatibility window
supported Python versions
contract versions
entry-point groups
~~~

Contract versions currently reported:

~~~text
plugin_api        = 1
external_workload = 1
references        = 1
observability     = 1
control_plane     = 1
~~~

This snapshot is intended for integration CI, diagnostics and compatibility automation.

## Independent package template

The repository includes:

~~~text
ecosystem-template/
~~~

This is a separately buildable wheel whose integration code imports only
`pyworkflowkit.ecosystem`.

Its dependency declaration is:

~~~text
pyworkflowkit >= 0.8.0b1, < 0.9
~~~

The template provides one workload entry point and demonstrates the minimum packaging
shape a third-party author needs.

## Artifact conformance

`scripts/qualify_ecosystem_sdk.py` performs:

~~~text
build/accept PyWorkflowKit wheel
build independent template wheel
create fresh virtualenv
install PyWorkflowKit wheel
install template wheel
discover real entry point
run SDK conformance
explicitly enable plugin
execute external workload
inspect ExternalRunRef evidence
serialize compatibility snapshot
uninstall template
verify entry point disappears
execute core-only workflow
~~~

The scenario runs outside the source checkout.

## Conformance matrix

Regular CI and Release Qualification run the ecosystem SDK scenario on:

~~~text
Python 3.11
Python 3.12
Python 3.13
~~~

Release Qualification uses the already-built PyWorkflowKit wheel.

This makes the supported matrix executable rather than documentary.

## Security and ownership

The SDK does not add:

~~~text
dynamic pip installation
automatic plugin enablement
plugin sandboxing
untrusted-code execution
scheduler
background daemon
marketplace
~~~

Installed plugins remain trusted Python code.

## Compatibility policy

The 0.8 SDK compatibility window is deliberately explicit.

An integration targeting:

~~~text
pyworkflowkit >= 0.8.0b1, < 0.9
~~~

may rely on the M52 ecosystem facade and contract snapshot for the 0.8 line.

Future 0.9 compatibility is not implied by M52; it must be qualified separately during
release-candidate stabilization.

## Relationship to M47-M51

~~~text
M47 external workload contract
       ↓
M48 portable evidence
       ↓
M49 observability contract
       ↓
M50 independent integration packages
       ↓
M51 control-plane provider
       ↓
M52 ecosystem SDK + conformance matrix
~~~

M52 adds author ergonomics and qualification, not new runtime semantics.

## Exit condition

M52 is complete when a third-party author can:

~~~text
import one ecosystem facade
build a registration with current Plugin API metadata
discover the correct entry-point group
validate registration and instance contracts
read a machine-compatible support matrix
build an independent wheel
install it beside a built PyWorkflowKit wheel
execute it
uninstall it
leave core workflows operational
repeat this on Python 3.11 / 3.12 / 3.13
~~~

## Next

After transverse 0.8 qualification and promotion to 0.8.0 stable, the next roadmap line is
0.9 release-candidate stabilization toward 1.0.
