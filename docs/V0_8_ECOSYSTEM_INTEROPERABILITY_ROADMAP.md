# PyWorkflowKit 0.8 — Ecosystem Interoperability Roadmap

Date: 2026-09-27

## Objective

The `0.8` line begins after the compatibility and stabilization work completed in
`0.7`.

`0.7` established executable contracts for:

~~~text
public Python API
deprecation policy
CLI machine contract
Plugin API
persistence and migration compatibility
release qualification
~~~

`0.8` must now prove that PyWorkflowKit can participate cleanly in a larger Python and
orchestration ecosystem without absorbing the responsibilities of that ecosystem.

The line focuses on:

~~~text
external workload interoperability
portable external references
observability interoperability
reference integration packages
control-plane provider boundaries
ecosystem conformance
~~~

The objective is not to turn PyWorkflowKit into a platform.

> **PyWorkflowKit 0.8 proves that the stable runtime contracts established in 0.7 can
> support independently packaged workloads, plugins, observability adapters and
> control-plane providers without expanding the core into an orchestration platform.**

## Product rule

~~~text
0.6 proved recovery
      ↓
0.7 froze core compatibility expectations
      ↓
0.8 proves ecosystem interoperability
      ↓
0.9 performs 1.0 release-candidate stabilization
      ↓
1.0 freezes the stable embedded runtime contract
~~~

## Architecture ownership rule

Every new capability must pass the ownership test:

~~~text
generic runtime necessity
    → CORE

optional infrastructure capability
    → ADAPTER / PLUGIN

specialized workload behavior
    → EXTERNAL PACKAGE / RUNTIME

governance / scheduling / UI
    → OCHESTRIX / EXTERNAL PLATFORM

unrelated capability
    → REJECT
~~~

The central guardrail remains:

> **PyWorkflowKit owns how to execute a generic dependency graph. It does not own the
> business semantics of workloads or the governance platform around them.**

## Ecosystem boundaries

### PyIngestKit

~~~text
PyWorkflowKit may USE PyIngestKit.

PyWorkflowKit core must NOT require PyIngestKit.

PyIngestKit must NOT require PyWorkflowKit.
~~~

A PyIngestKit job remains one atomic PyWorkflowKit workload:

~~~text
WorkflowRun
│
├── TaskRun generic_python
├── TaskRun ingest_companies
│      └── ExternalRunRef
│             provider = pyingestkit
│             external_run_id = ...
└── TaskRun generate_report
~~~

PyWorkflowKit must not reproduce the internal ingestion lifecycle.

### Ochestrix

The dependency direction remains:

~~~text
Ochestrix
    ↓
PyWorkflowKit Provider
    ↓
PyWorkflowKit Runtime
~~~

Ochestrix may consume stable workflow/run/event/manifest/reference contracts, but
PyWorkflowKit must not import Ochestrix ORM, IAM, registry, scheduling, or Django models.

### Other orchestration engines

A control plane may expose providers in parallel:

~~~text
PyWorkflowKitProvider
AirflowProvider
PrefectProvider
DagsterProvider
GitHubActionsProvider
~~~

Foreign executions are linked through references. They are not copied into the
PyWorkflowKit runtime model.

## Proposed 0.8 milestone sequence

| Milestone | Capability | Target |
|---|---|---|
| M47 | External Workload Interoperability Contract | 0.8.0a1 |
| M48 | External References & Portable Integration Evidence | 0.8.0a2 |
| M49 | Observability Interoperability | 0.8.0a3 |
| M50 | Reference Integration Packages | 0.8.0a4 |
| M51 | Control-Plane Provider Contract | 0.8.0a5 |
| M52 | Ecosystem SDK & Conformance Matrix | 0.8.0b1 |
| Qualification | Transverse ecosystem qualification | 0.8.0 |

## M47 — External Workload Interoperability Contract — 0.8.0a1

### Objective

Define the smallest generic contract required for a third-party runtime to behave as a
PyWorkflowKit workload without leaking its own domain model into the core.

The contract should cover:

~~~text
workload identity
invocation through RunContext
TaskResult normalization
ExternalRunRef creation
failure normalization
retry ownership
timeout / cancellation capability boundary
~~~

Conceptual flow:

~~~text
TaskDefinition
      │
      ▼
Workload Adapter
      │
      ├── invoke external runtime
      ├── normalize result
      └── normalize failure
      ▼
TaskResult
├── output
├── artifacts
└── external_refs
~~~

Retry ownership must be explicit. Nested runtimes must not accidentally multiply
attempts.

M47 is complete when:

~~~text
a third-party workload can be adapted without core imports from that third party
external execution identity can be preserved
TaskResult normalization is deterministic
retry ownership is explicit
failure categories are normalized
adapter construction has no hidden side effects
no business-specific TaskType enum is introduced
~~~

## M48 — External References & Portable Integration Evidence — 0.8.0a2

### Objective

Harden `ExternalRunRef` and `ArtifactReference` as portable interoperability contracts
without taking ownership of foreign payloads.

The contract must preserve:

~~~text
stable provider naming
external identifiers
URI semantics
JSON-portable metadata
redaction
serialization
manifest representation
lineage representation
~~~

A foreign run remains foreign:

~~~text
ExternalRunRef != WorkflowRun
~~~

Artifact payload storage remains external or plugin-owned.

M48 is complete when references survive serialization, persistence, manifest generation
and lineage reconstruction without importing foreign runtime schemas.

## M49 — Observability Interoperability — 0.8.0a3

### Objective

Standardize integration with observability ecosystems while keeping every telemetry
vendor optional.

Target:

~~~text
RuntimeEvent
    ↓
ObservabilityDispatcher
    ├── local logging
    ├── custom RuntimeEventSink
    ├── OpenTelemetry adapter
    ├── metrics bridge
    └── external platform adapter
~~~

OpenTelemetry, if implemented, remains an adapter/plugin rather than a mandatory core
dependency.

Correlation may connect:

~~~text
WorkflowRun
TaskRun
TaskAttempt
RuntimeEvent
ExternalRunRef
trace / span identifiers
~~~

but telemetry identifiers never replace PyWorkflowKit domain identities.

M49 is complete when telemetry failure cannot mutate workflow state, redaction remains
effective, and at least one optional reference adapter proves the contract.

## M50 — Reference Integration Packages — 0.8.0a4

### Objective

Exercise the interoperability contracts through realistic integrations outside the core.

Initial reference candidates:

~~~text
PyIngestKit adapter package
reference workload adapter
reference event sink
reference metadata plugin
~~~

PyIngestKit is the canonical specialized-runtime example:

~~~text
PyWorkflowKit Task
        ↓
PyIngestKit adapter
        ↓
PyIngestKit Job
        ↓
TaskResult + ExternalRunRef
~~~

From PyWorkflowKit's perspective the PyIngestKit job remains one task.

Reference packages must be independently installable and removable. Installing or
removing one integration must not alter unrelated core workflows.

## M51 — Control-Plane Provider Contract — 0.8.0a5

### Objective

Define how a control plane such as Ochestrix can operate PyWorkflowKit using only stable
public boundaries.

A provider may expose operations such as:

~~~text
validate workflow
inspect workflow definition
execute workflow
inspect run
list runtime events
retrieve manifest
retrieve lineage
request cancellation
assess recovery
resume eligible run
inspect runtime capabilities
~~~

The provider must exchange portable IDs, schemas, manifests, events, references,
statuses, capabilities and diagnostics.

It must not expose:

~~~text
SQLAlchemy sessions
ORM rows
Django models
private repositories
executor implementation objects
internal runtime services
~~~

Scheduling remains external.

## M52 — Ecosystem SDK & Conformance Matrix — 0.8.0b1

### Objective

Turn M47-M51 into a usable third-party authoring experience.

A plugin/integration author should be able to answer:

~~~text
How do I build an integration?
Which contracts may I rely on?
How do I test it?
Which PyWorkflowKit versions support it?
~~~

The ecosystem-facing surface may include:

~~~text
PluginDescriptor
entry-point groups
workload integration helpers
TaskResult
ExternalRunRef
ArtifactReference
RuntimeEventSink
MetadataStore
Executor
compatibility diagnostics
contract test helpers
~~~

External conformance must prove independently packaged integrations can:

~~~text
build their own wheel
install PyWorkflowKit wheel
install integration wheel
discover explicitly
validate compatibility
execute reference scenario
uninstall integration
leave core operational
~~~

## Transverse 0.8 qualification

After M52:

~~~text
M47 External Workload Contract
M48 External References
M49 Observability Interoperability
M50 Reference Integrations
M51 Control-Plane Provider Contract
M52 Ecosystem SDK / Conformance
        ↓
Transverse 0.8 Qualification
        ↓
0.8.0 stable
~~~

Mandatory transverse scenarios:

~~~text
A. PyWorkflowKit-only local workflow
B. third-party executor plugin
C. specialized external runtime workload
D. optional observability adapter
E. control-plane provider using only public contracts
F. broken optional integration isolated from core
~~~

## Compatibility requirements

`0.8` must preserve the stable `0.7` contracts unless an explicit deprecation path
exists.

Inherited stable-intent contracts include:

~~~text
package-root API
lifecycle enums
RuntimeEvent vocabulary
CLI machine contract
Plugin API
MetadataStore / UnitOfWork
RunManifest schema
persistence migration history
release qualification contract
~~~

No ecosystem feature justifies a silent compatibility break.

## Migration requirements

If `0.8` changes persistence:

~~~text
0003_retry_eligible_at
        ↓
0004_...
~~~

Published migrations 0001-0003 remain immutable.

The full historical SQLite/PostgreSQL upgrade matrix must continue to pass.

## Release qualification extension

The M46 Release Qualification workflow is extended rather than replaced.

0.8 qualification should retain:

~~~text
artifact build/install qualification
Python 3.11 / 3.12 / 3.13
reference contract snapshots
SQLite upgrade matrix
PostgreSQL upgrade matrix
security gates
~~~

and add:

~~~text
third-party plugin package build
external workload conformance
observability adapter conformance
provider contract conformance
integration failure isolation
~~~

## Security rules

Interoperability creates additional trust boundaries.

The line must preserve:

~~~text
no automatic plugin enablement
no automatic package installation
no shell=True
no secret leakage in events
no secret leakage in manifests
no secret leakage in plugin diagnostics
no untrusted-code sandbox claim
no plugin sandbox claim
~~~

Installed plugins remain trusted Python code unless a future architecture explicitly
changes that assumption.

## Dependency rule

New integrations should prefer independent packages or optional extras.

The following must not become core dependencies merely because an integration exists:

~~~text
OpenTelemetry
PyIngestKit
cloud SDKs
Ochestrix
vendor executors
business connectors
~~~

The minimal installation remains:

~~~text
pip install pyworkflowkit

required external services = 0
required scheduler = 0
required broker = 0
required web server = 0
~~~

## Explicit non-goals for 0.8

~~~text
scheduler
cron service
background orchestration daemon
distributed worker fleet
message broker platform
web UI
RBAC / IAM
multi-tenant control plane
enterprise workflow registry
connector marketplace
dynamic pip installation
plugin marketplace
Kubernetes control plane
AI agent framework
RAG runtime
business connector catalog
data catalog
exactly-once execution claims
~~~

## Rejected architecture patterns

~~~text
PyWorkflowKit imports Django
PyWorkflowKit imports Ochestrix models
PyWorkflowKit imports PyIngestKit in core
TaskDefinition gains provider-specific fields
PluginType becomes a vendor enum
RunContext becomes a service locator
ExternalRunRef copies complete foreign runtime state
ArtifactReference stores payload bytes
RuntimeEvent depends on OpenTelemetry classes
scheduler loop appears in application/runtime
plugin discovery automatically enables discovered code
~~~

## 0.8 exit condition

The line is complete when a third-party developer can:

~~~text
pip install pyworkflowkit
build an external integration
declare its compatibility
package it independently
install it independently
have PyWorkflowKit discover it explicitly
validate it without private imports
execute it
produce portable evidence
observe it
remove it
and still leave the core runtime operational
~~~

## Relationship with 0.9

`0.8` applies real ecosystem pressure to the contracts stabilized in `0.7`.

Its findings should reveal:

~~~text
missing abstractions
over-specific APIs
accidental coupling
packaging problems
compatibility ambiguities
poor extension ergonomics
~~~

Those findings feed `0.9`, whose primary role should be 1.0 release-candidate
stabilization rather than major new capability work.

## Canonical trajectory

~~~text
0.6  Recovery proved
        ↓
0.7  Compatibility made explicit
        ↓
0.8  Ecosystem interoperability proved
        ↓
0.9  1.0 contract stabilized
        ↓
1.0  Stable embeddable workflow runtime
~~~

## Immediate next step after 0.7.0 stable

~~~text
M47 — External Workload Interoperability Contract — 0.8.0a1
~~~

M47 should define the exact public protocol/value objects, retry ownership, failure
normalization, TaskResult/ExternalRunRef mapping, capability boundary and external
conformance tests before implementation begins.
