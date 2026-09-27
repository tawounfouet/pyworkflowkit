# PyWorkflowKit 0.8 Transverse Qualification

Status: stable release qualification for 0.8.0

## Objective

The 0.8 line is not considered complete merely because M47-M52 pass independently.

The stable release requires one cross-contract scenario proving that the ecosystem
boundaries compose in the same installed environment without forcing optional
integrations into the core.

The qualification operates on the built PyWorkflowKit wheel.

## Mandatory scenarios

~~~text
A. PyWorkflowKit-only local workflow
B. third-party executor plugin
C. specialized external runtime workload
D. optional observability adapter
E. control-plane provider using public contracts
F. broken optional integration isolated from core
~~~

## A — Core-only workflow

A normal local WorkflowRuntime execution must succeed while all optional third-party
packages are installed.

This proves ecosystem packages do not replace or disturb the default embedded runtime.

## B — Third-party executor plugin

The qualification builds an independent executor wheel.

Its implementation imports only the public ecosystem authoring facade:

~~~python
from pyworkflowkit.ecosystem import ...
~~~

The wheel is discovered through:

~~~text
pyworkflowkit.executors
~~~

It is explicitly enabled, validated through the ecosystem conformance helper, and used by
the core Runner to execute a complete WorkflowDefinition.

## C — Specialized external runtime

The qualification installs the real PyIngestKit 1.0.1 reference pinned to:

~~~text
a19264845e10769fb8fd8cd42c83193ae011f702
~~~

The independently packaged PyIngestKit adapter is discovered and explicitly enabled.

Its plugin instance is intentionally an adapter factory rather than an ExternalWorkload
itself.

This scenario therefore freezes an important distinction:

~~~text
PluginType.WORKLOAD
    = generic plugin category

ExternalWorkload
    = execution protocol for the produced workload
~~~

The adapter factory creates one ExternalWorkload, which is executed as one atomic
PyWorkflowKit task and emits a portable ExternalRunRef.

## D — Optional observability adapter

The independently packaged reference RuntimeEventSink is discovered and enabled.

A workflow executes through WorkflowRuntime, and the sink must receive exactly the
committed durable events.

Observability remains a secondary projection and does not own workflow state.

## E — Control-plane provider

WorkflowRuntimeProvider executes a schema-first workflow using the public control-plane
boundary.

The qualification validates:

~~~text
execution
manifest schema v1
lineage
capability negotiation
external scheduling ownership
~~~

No control-plane framework dependency is introduced.

## F — Broken optional integration isolation

A deliberately broken package publishes a valid entry-point declaration whose target
module does not exist.

The expected sequence is:

~~~text
package installed
      ↓
entry point discoverable without import
      ↓
core workflow succeeds
      ↓
explicit enable attempted
      ↓
plugin result = FAILED
      ↓
no plugin registered
      ↓
core workflow still succeeds
~~~

This proves discovery remains lazy and optional plugin failure is isolated.

## Qualification fixtures

~~~text
qualification-integrations/
├── reference-executor/
└── broken-optional/
~~~

These are release fixtures only. They are not production packages.

## Qualification harness

~~~text
scripts/qualify_v0_8_transverse.py
~~~

The harness:

~~~text
builds/accepts the PyWorkflowKit wheel
builds the qualification wheels
builds the M50 event/PyIngestKit adapter wheels
creates a clean virtual environment
installs the core wheel
installs real PyIngestKit
installs every optional fixture
runs A -> F in one environment
~~~

This is intentionally different from isolated milestone tests: it proves the complete
0.8 ecosystem works together.

## Historical compatibility gates

Promotion to 0.8.0 still requires all inherited gates:

~~~text
0.7 package-root compatibility
CLI machine contract
RunManifest schema v1
Plugin API v1
MetadataStore / UnitOfWork
immutable migrations 0001-0003
SQLite historical upgrades
PostgreSQL historical upgrades
wheel + sdist installation
Python 3.11 / 3.12 / 3.13
security gates
M50 reference packages
M51 control-plane provider
M52 ecosystem SDK matrix
~~~

## Persistence

0.8 introduces no database migration.

The migration head remains:

~~~text
0003_retry_eligible_at
~~~

## Stable outcome

When every gate passes, the release line is promoted:

~~~text
0.8.0b1
   ↓
transverse qualification
   ↓
0.8.0 stable
~~~

The next roadmap line is 0.9 release-candidate stabilization toward 1.0.
